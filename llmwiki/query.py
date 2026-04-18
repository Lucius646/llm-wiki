from typing import Optional
from pathlib import Path
from llmwiki.search import search_relevant_pages
from llmwiki.llm_client import synthesize_answer
from llmwiki.utils import build_frontmatter, generate_slug, get_date_prefix, update_index, add_log_entry
from llmwiki.git_utils import commit_changes
from llmwiki.config import settings

def query_wiki(question: str, save: bool = False, topic: Optional[str] = None) -> str:
    """
    Query the wiki and generate an answer with citations
    Args:
        question: User's question
        save: Whether to save the answer as a synthesis page
        topic: Topic category for the saved page，也会作为搜索关键词的补充
    Returns:
        Synthesized answer with citations
    """
    # 搜索相关页面
    search_query = question
    if topic:
        # 如果指定了topic，加入到搜索关键词里，提高相关性
        search_query = f"{topic} {question}"
    relevant_pages = search_relevant_pages(search_query)

    # 合成回答
    answer = synthesize_answer(question, relevant_pages)

    changed_files = []

    if save:
        # Save as synthesis page
        slug = generate_slug(question)
        date_prefix = get_date_prefix()
        if not topic:
            topic = "uncategorized"

        synthesis_dir = settings.wiki_dir / "synthesis" / topic.lower().replace(" ", "-")
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
        changed_files.append(str(synthesis_file_path.relative_to(settings.wiki_root)))

        # 更新index.md
        update_index(synthesis_file_path, question, "synthesis")
        changed_files.append("wiki/index.md")

        # 更新log.md
        log_details = [
            f"问题：{question}",
            f"生成页面：{synthesis_file_path.relative_to(settings.wiki_root)}",
            f"引用来源：{len(relevant_pages)}个页面"
        ]
        add_log_entry("query", f"回答问题：{question[:30]}{'...' if len(question) > 30 else ''}", log_details)
        changed_files.append("wiki/log.md")

        # 自动提交Git变更
        if settings.git_auto_commit:
            commit_msg = f"[query] 回答问题：{question[:50]}{'...' if len(question) > 50 else ''} | 变更{len(changed_files)}个页面"
            commit_changes(commit_msg, changed_files)

    return answer
