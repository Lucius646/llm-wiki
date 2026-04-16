from pathlib import Path
from typing import Dict, Any, Optional
from llmwiki.parsers import parse_markdown, parse_pdf, parse_docx, parse_web, parse_audio
from llmwiki.llm_client import analyze_content
from llmwiki.git_utils import commit_changes
from llmwiki.utils import generate_slug, get_date_prefix, build_frontmatter
from llmwiki.config import settings

def ingest_source(path: str, topic: Optional[str] = None, auto_approve: bool = False) -> Dict[str, Any]:
    """
    Ingest a source file or URL into the wiki

    Args:
        path: Local file path or URL
        topic: Topic category for the source
        auto_approve: Auto-approve changes without confirmation

    Returns:
        Ingestion result with changed pages information
    """
    # TODO: Implement full ingestion logic
    print(f"DEBUG: Ingesting {path}, topic: {topic}, auto_approve: {auto_approve}")

    # Identify source type and parse
    if path.startswith(("http://", "https://")):
        content, metadata = parse_web(path)
    else:
        file_path = Path(path)
        if not file_path.exists():
            raise ValueError(f"File not found: {path}")

        suffix = file_path.suffix.lower()
        if suffix in [".md", ".txt"]:
            content, metadata = parse_markdown(file_path)
        elif suffix == ".pdf":
            content, metadata = parse_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            content, metadata = parse_docx(file_path)
        elif suffix in [".mp3", ".wav", ".m4a", ".flac"]:
            content, metadata = parse_audio(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    # Auto-detect topic if not provided
    if not topic:
        # TODO: Use LLM to detect topic from content
        topic = "uncategorized"

    # Save raw source
    slug = generate_slug(metadata.get("title", Path(path).stem))
    date_prefix = get_date_prefix()
    raw_file_name = f"{date_prefix}-{slug}.md"
    raw_topic_dir = settings.get_raw_topic_dir(topic)
    raw_topic_dir.mkdir(exist_ok=True, parents=True)
    raw_file_path = raw_topic_dir / raw_file_name

    # Build raw source content
    raw_content = build_frontmatter({
        "title": metadata.get("title", slug),
        "source": path,
        "author": metadata.get("author", "Unknown"),
        "published_date": metadata.get("published_date", "Unknown"),
        "ingested_date": get_date_prefix(),
        "topic": topic
    }) + "\n" + content

    raw_file_path.write_text(raw_content, encoding="utf-8")

    # TODO: Analyze content with LLM, create/update wiki pages
    # TODO: Update index.md
    # TODO: Update log.md
    # TODO: Commit changes if enabled

    return {
        "changed_pages": 1,
        "new_pages": [str(raw_file_path.relative_to(settings.wiki_root))],
        "updated_pages": []
    }
