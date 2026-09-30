"""
Unit tests for MeetingSummarizer.
"""

from unittest.mock import AsyncMock, patch
import pytest

from diswhisper.summarizer.engine import MeetingSummarizer


@pytest.mark.anyio
async def test_summarize_empty_transcript():
    summarizer = MeetingSummarizer(provider="cloud", api_key="test_key")
    res = await summarizer.summarize_transcript("")
    assert "Cannot summarize an empty transcript" in res


@pytest.mark.anyio
async def test_summarize_cloud_missing_key():
    summarizer = MeetingSummarizer(provider="cloud", cloud_platform="groq", api_key="")
    res = await summarizer.summarize_transcript("Sample meeting speech text")
    assert "Missing API key" in res


@pytest.mark.anyio
async def test_summarize_cloud_mock():
    summarizer = MeetingSummarizer(provider="cloud", cloud_platform="groq", api_key="valid_test_key")

    mock_response = {
        "choices": [
            {
                "message": {
                    "content": "### 📌 Executive Summary\nGreat team meeting.\n\n### ✅ Action Items\n- [ ] Alice: Ship feature."
                }
            }
        ]
    }

    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_ctx = AsyncMock()
        mock_ctx.status = 200
        mock_ctx.json = AsyncMock(return_value=mock_response)
        mock_post.return_value.__aenter__.return_value = mock_ctx

        summary = await summarizer.summarize_transcript("Alice: Let's ship the feature.")
        assert "Executive Summary" in summary
        assert "Alice: Ship feature" in summary
