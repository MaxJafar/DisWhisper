"""Local REST and WebSocket IPC for the desktop companion."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from aiohttp import web
from pydantic import ValidationError

from diswhisper.config import public_config
from diswhisper.discord_setup import validate_bot_token
from diswhisper.models import download_model, get_model, model_inventory, ollama_models
from diswhisper.summarizer.engine import MeetingSummarizer

logger = logging.getLogger(__name__)


class DisWhisperApiServer:
    def __init__(self, bot: Any, host: str = "127.0.0.1", port: int = 8765):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = web.Application(middlewares=[self._request_middleware])
        self.runner = None
        self._ws_clients: set[web.WebSocketResponse] = set()
        self.download_state: dict[str, dict] = {}
        self._download_tasks: dict[str, asyncio.Task] = {}
        self._setup_routes()
        self.app.on_shutdown.append(self._shutdown)

    def _setup_routes(self) -> None:
        for method, route, handler in (
            ("GET", "/api/status", self.handle_get_status),
            ("GET", "/api/config", self.handle_get_config),
            ("POST", "/api/config", self.handle_update_config),
            ("GET", "/api/models", self.handle_get_models),
            ("POST", "/api/models/download", self.handle_download_model),
            ("GET", "/api/models/progress", self.handle_get_download_progress),
            ("POST", "/api/models/cancel", self.handle_cancel_download),
            ("POST", "/api/models/activate", self.handle_activate_model),
            ("POST", "/api/engine/switch", self.handle_switch_engine),
            ("POST", "/api/summarize", self.handle_summarize),
            ("GET", "/api/transcripts", self.handle_list_transcripts),
            ("GET", "/api/events", self.handle_websocket),
            ("POST", "/api/discord/validate", self.handle_validate_discord),
            ("POST", "/api/bot/start", self.handle_start_bot),
            ("POST", "/api/bot/stop", self.handle_stop_bot),
            ("POST", "/api/meeting/finish", self.handle_finish_meeting),
            ("POST", "/api/system/shutdown", self.handle_shutdown),
            ("GET", "/api/transcripts/{filename}", self.handle_read_transcript),
        ):
            self.app.router.add_route(method, route, handler)

    @web.middleware
    async def _request_middleware(
        self, request: web.Request, handler: Any
    ) -> web.StreamResponse:
        # Native companions send no Origin. Do not expose control of the bot to arbitrary websites.
        origin = request.headers.get("Origin")
        hostname = urlsplit("http://" + request.host).hostname
        if hostname not in ("localhost", "127.0.0.1", "::1"):
            return web.json_response({"error": "Only local companion requests are allowed"}, status=403)
        if origin and origin.rstrip("/") != f"{request.scheme}://{request.host}":
            return web.json_response(
                {"error": "Cross-origin requests are not allowed"}, status=403
            )
        try:
            if request.method == "OPTIONS":
                response = web.Response(status=204)
            else:
                response = await handler(request)
        except ValidationError as error:
            fields = [
                {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                for item in error.errors(include_input=False, include_url=False)
            ]
            return web.json_response(
                {"error": "Invalid configuration", "fields": fields}, status=400
            )
        except (ValueError, TypeError) as error:
            return web.json_response({"error": str(error)}, status=400)
        except web.HTTPException as error:
            return web.json_response({"error": error.reason}, status=error.status)
        except Exception:
            logger.exception(
                "Companion request failed: %s %s", request.method, request.path
            )
            return web.json_response(
                {"error": "Backend operation failed; see the bot log"}, status=500
            )
        if origin and not response.prepared:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    @staticmethod
    async def _body(request: web.Request) -> dict:
        try:
            body = await request.json()
        except (ValueError, UnicodeDecodeError):
            raise ValueError("Invalid JSON") from None
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object")
        return body

    async def broadcast_event(self, event_type: str, data: dict) -> None:
        payload = json.dumps(
            {
                "event": event_type,
                "data": data,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
        )

        async def send(ws: web.WebSocketResponse) -> None:
            try:
                await asyncio.wait_for(ws.send_str(payload), timeout=2)
            except Exception:
                self._ws_clients.discard(ws)

        # Disconnects can mutate the set while sends are awaited.
        await asyncio.gather(*(send(ws) for ws in tuple(self._ws_clients)))

    async def handle_get_status(self, request: web.Request) -> web.Response:
        now = datetime.datetime.now(tz=self.bot.start_time.tzinfo)
        vc = self.bot.active_vc
        connected = bool(vc and vc.is_connected())
        gpu_info = None
        if self.bot.engine.active_device == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    gpu_info = {
                        "allocated_mb": round(
                            torch.cuda.memory_allocated() / 1024**2, 1
                        ),
                        "reserved_mb": round(torch.cuda.memory_reserved() / 1024**2, 1),
                    }
            except ImportError:
                pass
        data = {
            "status": getattr(self.bot, "state", "online" if self.bot.is_ready() else "connecting"),
            "bot_user": str(self.bot.user) if self.bot.user else "Not Connected",
            "voice_connected": connected,
            "voice_channel": vc.channel.name if connected and vc.channel else None,
            "engine_name": self.bot.engine.engine_name,
            "model_name": self.bot.engine.model_name,
            "device": self.bot.engine.active_device,
            "compute_type": self.bot.engine.active_compute_type,
            "queue_depth": self.bot.queue.qsize() if self.bot.queue else 0,
            "active_speaker_buffers": self.bot.buffer_manager.active_user_count
            if self.bot.buffer_manager
            else 0,
            "uptime_seconds": int((now - self.bot.start_time).total_seconds()),
            "gpu_memory": gpu_info,
            "engine_loaded": getattr(self.bot, "engine_loaded", True),
            "error": getattr(self.bot, "last_error", ""),
            "token_configured": bool(self.bot.cfg.DISCORD_TOKEN),
            "language": self.bot.cfg.LANGUAGE or "auto",
            "managed": hasattr(self.bot, "start_bot"),
            "session_id": getattr(self.bot, "session_id", ""),
            "process_id": os.getpid(),
        }
        return web.json_response(data)

    async def handle_get_config(self, request: web.Request) -> web.Response:
        return web.json_response(public_config(self.bot.cfg))

    async def handle_update_config(self, request: web.Request) -> web.Response:
        updates = await self._body(request)
        await self.bot.update_configuration(updates)
        result = public_config(self.bot.cfg)
        await self.broadcast_event("config_updated", result)
        return web.json_response(
            {
                "status": "success",
                "config": result,
                "restart_required": bool(
                    set(updates)
                    & {
                        "DISCORD_TOKEN",
                        "GUILD_ID",
                        "ENABLE_API_SERVER",
                        "API_SERVER_HOST",
                        "API_SERVER_PORT",
                    }
                ),
            }
        )

    async def handle_get_models(self, request: web.Request) -> web.Response:
        return web.json_response({"models": await model_inventory(self.bot.cfg)})

    async def handle_download_model(self, request: web.Request) -> web.Response:
        body = await self._body(request)
        model = get_model(body.get("model_id"))
        if not model.downloadable:
            raise ValueError("Cloud providers do not require a model download")
        task = self._download_tasks.get(model.id)
        if task and not task.done():
            return web.json_response(
                {"status": "download_in_progress", "model_id": model.id}, status=202
            )
        self.download_state[model.id] = {
            "status": "downloading",
            "percent": None,
            "detail": "Queued",
        }
        self._download_tasks[model.id] = asyncio.create_task(
            self._download_model_task(model.id), name=f"model-download-{model.id}"
        )
        return web.json_response(
            {"status": "download_started", "model_id": model.id}, status=202
        )

    async def _download_model_task(self, model_id: str) -> None:
        config = self.bot.cfg.model_copy(deep=True)

        async def progress(percent: int | None, detail: str) -> None:
            self.download_state[model_id] = {
                "status": "downloading",
                "percent": percent,
                "detail": detail,
            }
            await self.broadcast_event(
                "download_progress",
                {"model_id": model_id, **self.download_state[model_id]},
            )

        try:
            await download_model(config, get_model(model_id), progress)
            state = {
                "status": "completed",
                "percent": 100,
                "detail": "Download complete",
            }
        except asyncio.CancelledError:
            self.download_state[model_id] = {"status": "cancelled", "percent": None}
            raise
        except Exception as error:
            logger.exception("Model download failed: %s", model_id)
            state = {"status": "failed", "percent": None, "error": str(error)}
        self.download_state[model_id] = state
        await self.broadcast_event("download_progress", {"model_id": model_id, **state})

    async def handle_get_download_progress(self, request: web.Request) -> web.Response:
        return web.json_response(self.download_state)

    async def handle_activate_model(self, request: web.Request) -> web.Response:
        body = await self._body(request)
        model = get_model(body.get("model_id"))
        if model.engine == "ollama":
            available, installed = await ollama_models(self.bot.cfg)
            if not available:
                raise ValueError("Ollama is unreachable. Start Ollama and try again.")
            if model.model_name not in installed:
                raise ValueError("Download this Ollama model before activating it")
        await self.bot.switch_engine(model.engine, model_id=model.id)
        return web.json_response({"status": "success", "model_id": model.id})

    async def handle_switch_engine(self, request: web.Request) -> web.Response:
        body = await self._body(request)
        target = body.get("engine")
        if not isinstance(target, str):
            raise ValueError("engine must be a string")
        await self.bot.switch_engine(target)
        engine = self.bot.engine
        return web.json_response(
            {
                "status": "success",
                "active_engine": engine.engine_name,
                "model": engine.model_name,
                "device": engine.active_device,
            }
        )

    async def handle_summarize(self, request: web.Request) -> web.Response:
        body = await self._body(request)
        text = body.get("transcript_text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("transcript_text must be a non-empty string")
        cfg = self.bot.cfg
        provider = body.get("provider") or cfg.SUMMARIZER_PROVIDER
        platform = body.get("cloud_platform") or cfg.CLOUD_STT_PROVIDER
        if provider not in ("local", "cloud") or platform not in ("groq", "openai"):
            raise ValueError("Unsupported summary provider")
        model = body.get("model") or (
            cfg.LOCAL_SUMMARIZER_MODEL
            if provider == "local"
            else cfg.SUMMARIZER_MODEL
            if platform == cfg.CLOUD_STT_PROVIDER
            else None
        )
        if model is not None and not isinstance(model, str):
            raise ValueError("model must be a string")
        summarizer = MeetingSummarizer(
            provider=provider,
            cloud_platform=platform,
            api_key=cfg.GROQ_API_KEY if platform == "groq" else cfg.OPENAI_API_KEY,
            model_name=model,
            local_llm_url=cfg.LOCAL_LLM_URL,
        )
        summary = await summarizer.summarize_transcript(text)
        return web.json_response({"status": "success", "summary": summary})

    async def handle_list_transcripts(self, request: web.Request) -> web.Response:
        items = []
        directory = self.bot.file_logger.output_dir
        if directory.is_dir():
            for path in sorted(
                directory.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True
            ):
                stat = path.stat()
                items.append(
                    {
                        "filename": path.name,
                        "path": str(path.resolve()),
                        "size_bytes": stat.st_size,
                        "modified": datetime.datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                    }
                )
        return web.json_response({"transcripts": items, "directory": str(directory.resolve())})

    async def handle_read_transcript(self, request: web.Request) -> web.Response:
        filename = request.match_info["filename"]
        directory = self.bot.file_logger.output_dir.resolve()
        path = (directory / filename).resolve()
        if Path(filename).name != filename or path.parent != directory or path.suffix != ".md":
            raise web.HTTPNotFound(reason="Transcript not found")
        if not path.is_file():
            raise web.HTTPNotFound(reason="Transcript not found")
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("This transcript is too large to preview. Open the local file instead.")
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return web.json_response({"filename": filename, "content": content})

    async def handle_cancel_download(self, request: web.Request) -> web.Response:
        body = await self._body(request)
        model = get_model(body.get("model_id"))
        task = self._download_tasks.get(model.id)
        if not task or task.done():
            raise ValueError("This model has no download to cancel.")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return web.json_response({"status": "cancelled", "model_id": model.id})

    async def handle_validate_discord(self, request: web.Request) -> web.Response:
        body = await self._body(request)
        token = body.get("token") or self.bot.cfg.DISCORD_TOKEN
        return web.json_response(await validate_bot_token(token))

    async def handle_start_bot(self, request: web.Request) -> web.Response:
        await self._body(request)
        if not hasattr(self.bot, "start_bot"):
            raise ValueError("This backend was started from the command line. Use companion mode to control it from the app.")
        await self.bot.start_bot()
        return web.json_response({"status": "starting"}, status=202)

    async def handle_stop_bot(self, request: web.Request) -> web.Response:
        await self._body(request)
        if not hasattr(self.bot, "stop_bot"):
            raise ValueError("This bot is managed by its terminal. Finish with /leave and stop it there.")
        await self.bot.stop_bot()
        return web.json_response({"status": "idle"})

    async def handle_finish_meeting(self, request: web.Request) -> web.Response:
        await self._body(request)
        active_bot = getattr(self.bot, "_bot", self.bot)
        if not active_bot or not active_bot.active_vc:
            raise ValueError("There is no active meeting to finish.")
        path = await active_bot._cleanup_voice_session("Meeting finished from DisWhisper")
        return web.json_response({"status": "finished", "filename": path.name if path else None})

    async def handle_shutdown(self, request: web.Request) -> web.Response:
        await self._body(request)
        if not hasattr(self.bot, "shutdown_requested"):
            raise ValueError("This backend is managed by its terminal.")
        self.bot.shutdown_requested.set()
        return web.json_response({"status": "stopping"})

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._ws_clients.add(ws)
        try:
            await ws.send_json(
                {
                    "event": "connected",
                    "data": {
                        "engine": self.bot.engine.engine_name,
                        "model": self.bot.engine.model_name,
                    },
                }
            )
            async for _ in ws:
                pass
        finally:
            self._ws_clients.discard(ws)
        return ws

    async def _shutdown(self, app: web.Application) -> None:
        tasks = list(self._download_tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(
            *(
                ws.close(code=1001, message=b"Backend stopping")
                for ws in tuple(self._ws_clients)
            ),
            return_exceptions=True,
        )
        self._ws_clients.clear()

    async def start(self) -> None:
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        await web.TCPSite(self.runner, self.host, self.port).start()
        logger.info("Companion IPC listening at http://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
