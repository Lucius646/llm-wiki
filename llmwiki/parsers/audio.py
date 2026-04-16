from pathlib import Path
from typing import Tuple, Dict, Any
import whisper
from llmwiki.config import settings

_model = None

def get_whisper_model():
    """Get the Whisper model instance"""
    global _model
    if _model is None:
        _model = whisper.load_model(settings.whisper_model)
    return _model

def parse_audio(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Transcribe audio file to text using Whisper

    Args:
        file_path: Path to the audio file

    Returns:
        Tuple of (transcribed_text, metadata)
    """
    model = get_whisper_model()
    result = model.transcribe(str(file_path))

    content = result["text"]

    metadata = {
        "title": file_path.stem,
        "author": "Unknown",
        "published_date": "Unknown",
        "source": str(file_path),
        "file_type": "audio",
        "language": result.get("language", "unknown"),
        "duration": result.get("duration", 0)
    }

    return content, metadata
