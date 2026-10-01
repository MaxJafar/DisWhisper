"""
Entry point for DisWhisper Discord Meeting Transcriber.
Initializes logging, loads configuration, prepares the local Whisper model,
and starts the Discord bot gateway connection.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from diswhisper.bot import DisWhisperBot
from diswhisper.config import load_config
from diswhisper.transcriber.factory import create_stt_engine


def setup_logging(level_name: str) -> None:
    """Configure structured logging output with timestamps."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence overly verbose external loggers
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DisWhisper - Real-time Discord Meeting Transcriber (SenseVoice & Whisper)"
    )
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to custom config.json file",
    )
    parser.add_argument(
        "--engine",
        "-e",
        type=str,
        default=None,
        choices=["sensevoice", "whisper", "vosk", "cloud", "groq", "openai"],
        help="Speech-to-text provider (choose models in the companion)",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default=None,
        help="Override Whisper model size (e.g. large-v3, small, medium)",
    )
    parser.add_argument(
        "--device",
        "-d",
        type=str,
        default=None,
        help="Override device (cuda or cpu)",
    )
    parser.add_argument("--companion", action="store_true", help="Run the desktop service, including setup and bot start/stop controls")
    parser.add_argument("--data-dir", type=Path, help="Folder for settings, models, logs, and transcripts")
    parser.add_argument("--session-id", default="", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.data_dir:
        args.data_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(args.data_dir.resolve())
        if not args.config:
            args.config = str(Path.cwd() / "config.json")

    # 1. Load configuration
    cfg = load_config(args.config)
    if args.engine:
        cfg.STT_ENGINE = args.engine
    if args.model:
        cfg.WHISPER_MODEL_SIZE = args.model
    if args.device:
        cfg.DEVICE = args.device

    # 2. Setup logging
    setup_logging(cfg.LOG_LEVEL)
    logger = logging.getLogger("DisWhisper")

    logger.info("==================================================")

    if args.companion:
        from diswhisper.runtime import CompanionRuntime

        try:
            asyncio.run(CompanionRuntime(cfg, args.session_id).run())
        except KeyboardInterrupt:
            logger.info("DisWhisper stopped.")
        return
    logger.info("  DisWhisper - Discord Meeting Transcriber        ")
    logger.info("==================================================")

    # 3. Validate Token
    if not cfg.DISCORD_TOKEN or cfg.DISCORD_TOKEN.strip() == "":
        logger.error(
            "DISCORD_TOKEN is missing! Please configure it in .env or config.json.\n"
            "Example in .env:\n"
            "  DISCORD_TOKEN=your_token_here\n\n"
            "To obtain a token, create a bot at https://discord.com/developers/applications"
        )
        sys.exit(1)

    # 4. Initialize Local STT Engine
    logger.info(f"Initializing STT engine (Engine: {cfg.STT_ENGINE}, Device: {cfg.DEVICE})...")
    try:
        from diswhisper.models import download_model, get_model, is_downloaded
        from diswhisper.runtime import selected_model_id

        try:
            selected = get_model(selected_model_id(cfg))
        except ValueError:
            selected = None  # Keep custom/legacy Whisper identifiers usable in the CLI.
        if selected and selected.category == "local_stt" and not is_downloaded(cfg, selected):
            async def progress(percent, detail):
                logger.info("%s%s", detail, f" ({percent}%)" if percent is not None else "")

            asyncio.run(download_model(cfg, selected, progress))
        engine = create_stt_engine(cfg)
    except Exception as e:
        logger.critical(f"Failed to initialize STT engine: {e}", exc_info=True)
        sys.exit(1)

    # 5. Launch Bot
    logger.info("Starting DisWhisper bot client...")
    bot = DisWhisperBot(config=cfg, engine=engine)

    try:
        bot.run(cfg.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("DisWhisper stopped by user.")
    except Exception as e:
        logger.critical(f"Bot execution terminated with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
