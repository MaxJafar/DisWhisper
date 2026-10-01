"""
Meeting Transcript Exporter and File Logger.
Records session utterances with timestamps and generates clean Markdown meeting logs.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path
from typing import Optional, Set

logger = logging.getLogger(__name__)


class TranscriptFileLogger:
    """
    Persists live transcript utterances into markdown files in the transcripts/ directory.
    """

    def __init__(self, output_dir: str | Path = "transcripts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.session_id: Optional[str] = None
        self.channel_name: Optional[str] = None
        self.start_time: Optional[datetime.datetime] = None
        self.file_path: Optional[Path] = None
        self.speakers: Set[str] = set()
        self.total_utterances: int = 0

    def start_session(self, channel_name: str, engine_name: str = "DisWhisper") -> Path:
        """Start a new meeting transcription logging session."""
        self.channel_name = channel_name
        self.start_time = datetime.datetime.now()
        self.session_id = self.start_time.strftime("%Y-%m-%d_%H-%M-%S_%f")
        self.file_path = self.output_dir / f"meeting_{self.session_id}.md"
        self.speakers.clear()
        self.total_utterances = 0

        header = (
            f"# Meeting Transcript: #{channel_name}\n\n"
            f"- **Date & Time:** {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Transcriber:** {engine_name}\n\n"
            f"## Live Conversation Log\n\n"
        )
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(header)
            logger.info(f"Started transcript file: {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to create transcript file: {e}")
            self.file_path = None
            self.start_time = None
            raise RuntimeError(
                "Cannot create the transcript file. Check output directory permissions."
            ) from e

        return self.file_path

    def log_utterance(self, display_name: str, text: str, timestamp: float) -> None:
        """Append an utterance to the active transcript session."""
        if not self.file_path:
            return

        dt = datetime.datetime.fromtimestamp(timestamp)
        time_str = dt.strftime("%H:%M:%S")

        entry = f"**[{time_str}] {display_name}:** {text}\n\n"
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(entry)
            self.speakers.add(display_name)
            self.total_utterances += 1
        except Exception as e:
            logger.error(f"Failed to write to transcript file: {e}")

    def end_session(self) -> Optional[Path]:
        """Finalize the transcript session with metadata summary."""
        if not self.file_path or not self.start_time:
            return None

        end_time = datetime.datetime.now()
        duration = end_time - self.start_time
        duration_minutes = duration.total_seconds() / 60.0

        summary = (
            f"---\n\n"
            f"### Meeting Summary\n"
            f"- **Duration:** {duration_minutes:.1f} minutes\n"
            f"- **Ended At:** {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- **Participants:** {', '.join(sorted(self.speakers)) if self.speakers else 'None'}\n"
            f"- **Total Utterances:** {self.total_utterances}\n"
        )
        try:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(summary)
            logger.info(f"Finalized meeting transcript: {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to finalize transcript file: {e}")

        final_path = self.file_path
        self.file_path = None
        self.session_id = None
        return final_path
