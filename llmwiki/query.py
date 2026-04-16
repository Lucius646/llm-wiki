from typing import Optional
from llmwiki.search import search_relevant_pages
from llmwiki.llm_client import synthesize_answer
from llmwiki.utils import build_frontmatter, generate_slug, get_date_prefix
from llmwiki.git_utils import commit_changes
from llmwiki.config import settings

def query_wiki(question: str, save: bool = False, topic: Optional[str] = None) -> str:
    """
    Query the wiki and generate an answer with citations

    Args:
        question: User's question
        save: Whether to save the answer as a synthesis page
        topic: Topic category for the saved page

    Returns:
        Synthesized answer with citations
    """
    # TODO: Implement full query logic
    print(f"DEBUG: Querying: {question}, save: {save}, topic: {topic}")

    # Search relevant pages
    relevant_pages = search_relevant_pages(question)

    # Synthesize answer
    answer = synthesize_answer(question, relevant_pages)

    if save:
        # Save as synthesis page
        slug = generate_slug(question)
        date_prefix = get_date_prefix()
        if not topic:
            topic = "uncategorized"

        synthesis_dir = settings.wiki_dir / "synthesis" / topic
        synthesis_dir.mkdir(exist_ok=True, parents=True)
        synthesis_file_path = synthesis_dir / f"{date_prefix}-{slug}.md"

        frontmatter = {
            "title": question,
            "type": "synthesis",
            "tags": [],
            "created_at": get_date_prefix(),
            "updated_at": get_date_prefix(),
            "source_count": len(relevant_pages)
        }

        content = build_frontmatter(frontmatter) + "\n" + answer
        synthesis_file_path.write_text(content, encoding="utf-8")

        # TODO: Update index.md
        # TODO: Update log.md
        # TODO: Commit changes if enabled

    return answer
