"""
Local REST and WebSocket IPC Server for DisWhisper Companion Apps.
Exposes endpoints for status, live streaming, configuration, model downloads,
and AI meeting summarization on http://127.0.0.1:8765.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from aiohttp import web

from diswhisper.config import Config
from diswhisper.summarizer.engine import MeetingSummarizer
from diswhisper.transcriber.factory import create_stt_engine

logger = logging.getLogger(__name__)


class DisWhisperApiServer:
    """
    Embedded REST and WebSocket server for desktop companion applications.
    """

    def __init__(self, bot: Any, host: str = "127.0.0.1", port: int = 8765):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self._ws_clients: Set[web.WebSocketResponse] = set()

        # Model download progress tracking: {model_name: {"status": "idle"|"downloading"|"completed", "percent": int}}
        self.download_state: Dict[str, Dict[str, Any]] = {}

        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_get("/api/status", self.handle_get_status)
        self.app.router.add_get("/api/config", self.handle_get_config)
        self.app.router.add_post("/api/config", self.handle_update_config)
        self.app.router.add_get("/api/models", self.handle_get_models)
        self.app.router.add_post("/api/models/download", self.handle_download_model)
        self.app.router.add_get("/api/models/progress", self.handle_get_download_progress)
        self.app.router.add_post("/api/engine/switch", self.handle_switch_engine)
        self.app.router.add_post("/api/summarize", self.handle_summarize)
        self.app.router.add_get("/api/transcripts", self.handle_list_transcripts)
        self.app.router.add_get("/api/events", self.handle_websocket)

        # CORS preflight middleware
        self.app.middlewares.append(self._cors_middleware)

    @web.middleware
    async def _cors_middleware(self, request: web.Request, handler: Any) -> web.Response:
        if request.method == "OPTIONS":
            response = web.Response(status=200)
        else:
            try:
                response = await handler(request)
            except web.HTTPException as ex:
                response = ex

        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcast real-time event to all connected WebSocket clients."""
        if not self._ws_clients:
            return

        payload = json.dumps({"event": event_type, "data": data, "timestamp": datetime.datetime.now().isoformat()})
        disconnected = set()
        for ws in self._ws_clients:
            try:
                await ws.send_str(payload)
            except Exception:
                disconnected.add(ws)

        for ws in disconnected:
            self._ws_clients.discard(ws)

    # Handlers
    async def handle_get_status(self, request: web.Request) -> web.Response:
        uptime = (datetime.datetime.now() - self.bot.start_time).total_seconds()
        vc_connected = bool(self.bot.active_vc and self.bot.active_vc.is_connected())
        vc_name = self.bot.active_vc.channel.name if vc_connected and self.bot.active_vc.channel else None

        gpu_info = None
        try:
            import torch
            if torch.cuda.is_available():
                gpu_info = {
                    "allocated_mb": round(torch.cuda.memory_allocated() / (1024**2), 1),
                    "reserved_mb": round(torch.cuda.memory_reserved() / (1024**2), 1),
                }
        except ImportError:
            pass

        data = {
            "status": "online",
            "bot_user": str(self.bot.user) if self.bot.user else "Not Connected",
            "voice_connected": vc_connected,
            "voice_channel": vc_name,
            "engine_name": self.bot.engine.engine_name,
            "model_name": self.bot.engine.model_name,
            "device": self.bot.engine.active_device,
            "compute_type": self.bot.engine.active_compute_type,
            "queue_depth": self.bot.queue.qsize() if self.bot.queue else 0,
            "active_speaker_buffers": self.bot.buffer_manager.active_user_count if self.bot.buffer_manager else 0,
            "uptime_seconds": int(uptime),
            "gpu_memory": gpu_info,
        }
        return web.json_response(data)

    async def handle_get_config(self, request: web.Request) -> web.Response:
        # Exclude secrets or mask them partially
        cfg_dict = self.bot.cfg.model_dump()
        if cfg_dict.get("DISCORD_TOKEN"):
            token = cfg_dict["DISCORD_TOKEN"]
            cfg_dict["DISCORD_TOKEN_MASKED"] = f"{token[:6]}...{token[-4:]}" if len(token) > 10 else "***"
        return web.json_response(cfg_dict)

    async def handle_update_config(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Update in-memory config
        for k, v in data.items():
            if hasattr(self.bot.cfg, k):
                setattr(self.bot.cfg, k, v)

        # Also persist to config.json
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(self.bot.cfg.model_dump(), f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save config.json: {e}")

        await self.broadcast_event("config_updated", self.bot.cfg.model_dump())
        return web.json_response({"status": "success", "config": self.bot.cfg.model_dump()})

    async def handle_get_models(self, request: web.Request) -> web.Response:
        """List local and cloud models and their availability."""
        models = [
            {
                "id": "sensevoice",
                "name": "Alibaba SenseVoice Small (int8)",
                "category": "local_stt",
                "latency": "< 100ms",
                "size_mb": 120,
                "features": ["Ultra-fast streaming", "Emotion detection (😄, 😢)", "Audio events (😂, 👏, 🎵)"],
                "languages": ["English", "Chinese", "Cantonese", "Japanese", "Korean"],
                "downloaded": True,
            },
            {
                "id": "whisper-large-v3",
                "name": "OpenAI Whisper Large-v3",
                "category": "local_stt",
                "latency": "~1.0s",
                "size_mb": 3100,
                "features": ["Universal accuracy", "99+ Languages", "Heavy accents"],
                "languages": ["Multilingual (99+ languages including Russian)"],
                "downloaded": False,
            },
            {
                "id": "whisper-large-v3-turbo",
                "name": "OpenAI Whisper Large-v3 Turbo",
                "category": "local_stt",
                "latency": "~0.5s",
                "size_mb": 1600,
                "features": ["4x Faster than Large-v3", "Low VRAM", "High quality"],
                "languages": ["Multilingual (99+ languages)"],
                "downloaded": False,
            },
            {
                "id": "cloud-groq",
                "name": "Groq Cloud Whisper (LPU)",
                "category": "cloud_stt",
                "latency": "~200ms",
                "size_mb": 0,
                "features": ["Ultra-fast cloud inference", "Zero local GPU/VRAM needed"],
                "languages": ["Multilingual (99+ languages)"],
                "downloaded": True,
            },
            {
                "id": "local-llm-ollama",
                "name": "Ollama Local LLM (Llama 3.2 / Qwen 2.5)",
                "category": "local_llm",
                "latency": "~2-5s",
                "size_mb": 2000,
                "features": ["100% Private local meeting summaries", "Action items", "Offline"],
                "languages": ["Multilingual"],
                "downloaded": False,
            },
        ]
        return web.json_response({"models": models})

    async def handle_download_model(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            model_id = body.get("model_id", "sensevoice")
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        # Trigger async background download task
        asyncio.create_task(self._download_model_task(model_id))
        return web.json_response({"status": "download_started", "model_id": model_id})

    async def _download_model_task(self, model_id: str) -> None:
        self.download_state[model_id] = {"status": "downloading", "percent": 10}
        await self.broadcast_event("download_progress", {"model_id": model_id, "percent": 10, "status": "downloading"})

        try:
            if "sensevoice" in model_id.lower():
                from huggingface_hub import hf_hub_download
                repo = self.bot.cfg.SENSEVOICE_MODEL_ID
                self.download_state[model_id]["percent"] = 40
                await self.broadcast_event("download_progress", {"model_id": model_id, "percent": 40, "status": "downloading"})

                await asyncio.to_thread(hf_hub_download, repo_id=repo, filename="model.int8.onnx")
                self.download_state[model_id]["percent"] = 80
                await self.broadcast_event("download_progress", {"model_id": model_id, "percent": 80, "status": "downloading"})

                await asyncio.to_thread(hf_hub_download, repo_id=repo, filename="tokens.txt")
            elif "whisper" in model_id.lower():
                from faster_whisper import download_model
                await asyncio.to_thread(download_model, model_id)

            self.download_state[model_id] = {"status": "completed", "percent": 100}
            await self.broadcast_event("download_progress", {"model_id": model_id, "percent": 100, "status": "completed"})
            logger.info(f"Model {model_id} downloaded successfully.")
        except Exception as e:
            logger.error(f"Download failed for {model_id}: {e}")
            self.download_state[model_id] = {"status": "failed", "error": str(e)}
            await self.broadcast_event("download_progress", {"model_id": model_id, "status": "failed", "error": str(e)})

    async def handle_get_download_progress(self, request: web.Request) -> web.Response:
        return web.json_response(self.download_state)

    async def handle_switch_engine(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            target_engine = body.get("engine", "sensevoice")
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        try:
            new_engine = create_stt_engine(self.bot.cfg, engine_type_override=target_engine)
            self.bot.engine = new_engine
            if self.bot.worker:
                self.bot.worker.engine = new_engine

            self.bot.cfg.STT_ENGINE = target_engine
            await self.broadcast_event("engine_switched", {
                "engine_name": new_engine.engine_name,
                "model_name": new_engine.model_name,
                "device": new_engine.active_device,
            })
            return web.json_response({
                "status": "success",
                "active_engine": new_engine.engine_name,
                "model": new_engine.model_name,
                "device": new_engine.active_device,
            })
        except Exception as e:
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def handle_summarize(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            transcript_text = body.get("transcript_text", "")
            provider = body.get("provider", self.bot.cfg.SUMMARIZER_PROVIDER)
            model = body.get("model", self.bot.cfg.SUMMARIZER_MODEL)
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        summarizer = MeetingSummarizer(
            provider=provider,
            cloud_platform=self.bot.cfg.CLOUD_STT_PROVIDER,
            api_key=self.bot.cfg.GROQ_API_KEY if self.bot.cfg.CLOUD_STT_PROVIDER == "groq" else self.bot.cfg.OPENAI_API_KEY,
            model_name=model,
            local_llm_url=self.bot.cfg.LOCAL_LLM_URL,
        )

        summary_md = await summarizer.summarize_transcript(transcript_text)
        return web.json_response({"status": "success", "summary": summary_md})

    async def handle_list_transcripts(self, request: web.Request) -> web.Response:
        transcript_dir = Path("transcripts")
        items = []
        if transcript_dir.is_dir():
            for p in sorted(transcript_dir.glob("*.md"), key=os.path.getmtime, reverse=True):
                items.append({
                    "filename": p.name,
                    "path": str(p.absolute()),
                    "size_bytes": p.stat().st_size,
                    "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
                })
        return web.json_response({"transcripts": items})

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info(f"Companion app WebSocket connected ({len(self._ws_clients)} active).")

        # Send initial status snapshot
        await ws.send_json({
            "event": "connected",
            "data": {"engine": self.bot.engine.engine_name, "model": self.bot.engine.model_name},
        })

        try:
            async for msg in ws:
                pass
        finally:
            self._ws_clients.discard(ws)
            logger.info("Companion app WebSocket disconnected.")

        return ws

    async def start(self) -> None:
        """Start the API server asynchronously."""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"DisWhisper Companion IPC server running on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the API server."""
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            logger.info("DisWhisper Companion IPC server stopped.")
