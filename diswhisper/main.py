"""
Entry point for DisWhisper Discord Meeting Transcriber.
Initializes logging, loads configuration, prepares the local Whisper model,
and starts the Discord bot gateway connection.
"""

from __future__ import annotations

import argparse
import logging
import sys

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
        choices=["sensevoice", "whisper"],
        help="Speech-to-text backend engine ('sensevoice' or 'whisper')",
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
    args = parser.parse_args()

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
