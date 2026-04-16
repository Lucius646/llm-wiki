from pathlib import Path
from typing import Tuple, Dict, Any
from docx import Document

def parse_docx(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Extract text content from Word document

    Args:
        file_path: Path to the .docx file

    Returns:
        Tuple of (content, metadata)
    """
    doc = Document(file_path)
    content = "\n\n".join([paragraph.text for paragraph in doc.paragraphs])

    metadata = {
        "title": doc.core_properties.title or file_path.stem,
        "author": doc.core_properties.author or "Unknown",
        "published_date": doc.core_properties.created.strftime('%Y-%m-%d') if doc.core_properties.created else "Unknown",
        "source": str(file_path),
        "file_type": "docx",
        "word_count": doc.core_properties.words or 0
    }

    return content, metadata
