from pathlib import Path
from typing import Tuple, Dict, Any
from llmwiki.utils import extract_frontmatter

def parse_markdown(file_path: Path) -> Tuple[str, Dict[str, Any]]:
    """
    Parse markdown or text file content

    Args:
        file_path: Path to the markdown/txt file

    Returns:
        Tuple of (content, metadata)
    """
    content = file_path.read_text(encoding="utf-8")
    frontmatter, body = extract_frontmatter(content)

    metadata = {
        "title": frontmatter.get("title", file_path.stem),
        "author": frontmatter.get("author", "Unknown"),
        "published_date": frontmatter.get("published_date", "Unknown"),
        "source": str(file_path),
        "file_type": "markdown"
    }

    return body, metadata
