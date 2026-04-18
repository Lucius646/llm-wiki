import os
from typing import Dict, Any, List, Tuple
from pathlib import Path
import re
from llmwiki.utils import extract_frontmatter, build_frontmatter, generate_slug, get_date_prefix, update_index, add_log_entry
from llmwiki.git_utils import commit_changes
from llmwiki.config import settings
from llmwiki.backlinks import parse_obsidian_links, _get_all_page_titles

def _get_all_wiki_pages() -> List[Tuple[Path, str, Dict[str, Any], str]]:
    """获取所有wiki页面的路径、相对路径、元数据和内容"""
    pages = []
    for root, _, files in os.walk(settings.wiki_dir):
        for file in files:
            if file.endswith(".md") and not file.startswith(".") and file not in ["index.md", "log.md"]:
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(encoding="utf-8")
                    frontmatter, body = extract_frontmatter(content)
                    rel_path = str(file_path.relative_to(settings.wiki_dir)).replace("\\", "/")
                    pages.append((file_path, rel_path, frontmatter, body))
                except Exception as e:
                    print(f"Warning: Failed to read {file_path}: {e}")
    return pages

def _extract_internal_links(content: str) -> List[Tuple[str, str, str]]:
    """
    提取内容中的所有内部链接，包括普通Markdown链接和Obsidian双链
    返回(链接文本, 目标路径, 链接类型: 'markdown'/'obsidian')
    """
    links = []
    # 1. 匹配普通Markdown链接 [文本](路径)，排除外部链接
    md_pattern = re.compile(r'\[([^\]]+)\]\((?!http|https)([^)]+)\)')
    md_matches = md_pattern.findall(content)
    for text, target in md_matches:
        links.append((text, target, "markdown"))

    # 2. 匹配Obsidian双链 [[目标页面|别名]] 或 [[目标页面]]
    obsidian_links = parse_obsidian_links(content)
    for link in obsidian_links:
        links.append((link["text"], link["target"], "obsidian"))

    return links

def lint_wiki(auto_fix: bool = False, generate_report: bool = True) -> Dict[str, Any]:
    """
    Run health check on the wiki

    Args:
        auto_fix: Whether to auto-fix repairable issues
        generate_report: Whether to generate a check report

    Returns:
        Lint result with issue counts and report
    """
    issues = []
    fixed_count = 0
    changed_files = []

    # 获取所有页面
    all_pages = _get_all_wiki_pages()
    all_page_paths = {rel_path for _, rel_path, _, _ in all_pages}
    all_page_titles = {frontmatter.get("title", "").lower() for _, _, frontmatter, _ in all_pages}

    # 1. 检测死链
    all_links = []
    title_map = _get_all_page_titles()  # 获取所有页面标题到路径的映射

    for file_path, rel_path, frontmatter, body in all_pages:
        links = _extract_internal_links(body)
        for link_text, link_target, link_type in links:
            all_links.append((rel_path, link_text, link_target, link_type))
            # 检查链接目标是否存在
            target_path = link_target.strip()
            if not target_path:
                continue

            exists = False
            if link_type == "markdown":
                # Markdown链接检查路径是否存在
                abs_target = settings.wiki_dir / target_path
                if abs_target.exists() or abs_target.with_suffix(".md").exists():
                    exists = True
            elif link_type == "obsidian":
                # Obsidian双链检查是否有对应标题的页面
                if target_path.lower() in title_map:
                    exists = True

            if not exists:
                issues.append({
                    "type": "dead_link",
                    "page": rel_path,
                    "link_text": link_text,
                    "target": target_path,
                    "link_type": link_type,
                    "details": f"{'双链' if link_type == 'obsidian' else '链接'} [{link_text}]{'' if link_type == 'obsidian' else f'({target_path})'} 指向的页面不存在",
                    "fixable": True
                })

    # 2. 检测孤立页面（没有被其他任何页面链接的页面）
    linked_pages = set()
    for _, _, link_target, link_type in all_links:
        if link_type == "markdown":
            # Markdown链接的目标是路径
            target_path = link_target.strip()
            abs_target = settings.wiki_dir / target_path
            if abs_target.exists():
                rel_target = str(abs_target.relative_to(settings.wiki_dir)).replace("\\", "/")
                linked_pages.add(rel_target)
            elif abs_target.with_suffix(".md").exists():
                rel_target = str(abs_target.with_suffix(".md").relative_to(settings.wiki_dir)).replace("\\", "/")
                linked_pages.add(rel_target)
        elif link_type == "obsidian":
            # Obsidian双链的目标是标题，需要转换为路径
            if link_target.lower() in title_map:
                linked_pages.add(title_map[link_target.lower()])

    for _, rel_path, _, _ in all_pages:
        if rel_path not in linked_pages and not rel_path.startswith("synthesis/"):
            # 排除synthesis页面，它们通常是回答，不需要被其他页面引用
            issues.append({
                "type": "isolated_page",
                "page": rel_path,
                "details": f"页面 {rel_path} 没有被任何其他页面引用",
                "fixable": False
            })

    # 3. 检测缺失页面：内容中提到的重要概念/实体没有对应页面
    # 简单实现：检测所有链接文本，检查是否有对应的页面标题
    mentioned_concepts = set()
    for _, link_text, _, _ in all_links:
        if len(link_text) > 1:
            mentioned_concepts.add(link_text.lower())

    # 还可以检测内容中出现的专有名词，这里简化处理
    for concept in mentioned_concepts:
        if concept not in all_page_titles and f"{concept}.md" not in all_page_paths:
            # 检查是否有对应的页面
            found = False
            for _, _, frontmatter, _ in all_pages:
                title = frontmatter.get("title", "").lower()
                if concept in title or title in concept:
                    found = True
                    break
            if not found:
                issues.append({
                    "type": "missing_page",
                    "target": concept,
                    "details": f"提到的概念/实体 '{concept}' 没有对应的Wiki页面",
                    "fixable": True
                })

    # 4. 检测内容冲突（简化实现：检查相似标题的页面描述冲突）
    # 先按关键词分组
    title_keywords = {}
    for file_path, rel_path, frontmatter, body in all_pages:
        title = frontmatter.get("title", "").lower()
        if title:
            # 提取关键词
            keywords = re.findall(r'[\w\u4e00-\u9fff]+', title)
            for kw in keywords:
                if len(kw) > 2:  # 只保留长度大于2的关键词
                    if kw not in title_keywords:
                        title_keywords[kw] = []
                    title_keywords[kw].append((rel_path, title, body))

    # 检查有相同关键词的页面
    for kw, pages in title_keywords.items():
        if len(pages) >= 2:
            # 有多个包含相同关键词的页面，可能存在冲突
            # 简单检查内容是否有冲突（比如相同实体的发布时间、版本号不同）
            # 这里简化处理，直接标记可能的冲突
            issues.append({
                "type": "content_conflict",
                "page": pages[0][0],
                "related_pages": [p[0] for p in pages[1:]],
                "details": f"存在多个包含关键词 '{kw}' 的页面，可能存在内容冲突：{', '.join([p[0] for p in pages])}",
                "fixable": False
            })

    # 自动修复
    if auto_fix:
        fix_result = fix_lint_issues(issues, fix_types=["dead_link", "missing_page"])
        fixed_count = fix_result["fixed_count"]
        changed_files.extend(fix_result["changed_files"])

    # 生成报告
    report = "# Wiki健康检查报告\n\n"
    report += f"检查时间：{get_date_prefix()}\n"
    report += f"总问题数：{len(issues)}\n"
    report += f"已修复数：{fixed_count}\n\n"

    report += "## 问题列表\n"
    issue_types = {
        "dead_link": "🔗 死链",
        "isolated_page": "🏝️ 孤立页面",
        "missing_page": "📄 缺失页面",
        "content_conflict": "⚠️ 内容冲突"
    }

    for issue_type, type_name in issue_types.items():
        type_issues = [i for i in issues if i["type"] == issue_type]
        if type_issues:
            report += f"\n### {type_name} ({len(type_issues)}个)\n"
            for issue in type_issues:
                report += f"- {issue['details']}\n"
                if issue.get("page"):
                    report += f"  位置：{issue['page']}\n"

    # 记录日志
    log_details = [
        f"总问题数：{len(issues)}",
        f"已修复数：{fixed_count}"
    ]
    add_log_entry("lint", f"健康检查 | 发现{len(issues)}个问题，修复{fixed_count}个", log_details)
    changed_files.append("wiki/log.md")

    # 自动提交Git变更
    if changed_files and settings.git_auto_commit:
        commit_msg = f"[lint] 健康检查 | 修复{fixed_count}个问题"
        commit_changes(commit_msg, changed_files)

    return {
        "total_issues": len(issues),
        "fixed_issues": fixed_count,
        "report": report,
        "issues": issues
    }

def fix_lint_issues(issues: List[Dict[str, Any]] = None, fix_types: List[str] = None) -> Dict[str, Any]:
    """
    自动修复可修复的lint问题

    Args:
        issues: 问题列表，如果为None则先运行lint获取问题
        fix_types: 要修复的问题类型，默认修复所有可修复类型

    Returns:
        修复结果，包含修复数量和变更的文件列表
    """
    if issues is None:
        lint_result = lint_wiki(auto_fix=False)
        issues = lint_result["issues"]

    if fix_types is None:
        fix_types = ["dead_link", "missing_page"]

    fixed_count = 0
    changed_files = []

    # 先获取所有页面
    all_pages = _get_all_wiki_pages()
    all_page_paths = {rel_path for _, rel_path, _, _ in all_pages}

    # 修复死链：尝试查找最匹配的页面
    if "dead_link" in fix_types:
        dead_links = [i for i in issues if i["type"] == "dead_link"]
        for link in dead_links:
            # 尝试查找最匹配的页面
            link_text = link["link_text"].lower()
            best_match = None
            highest_score = 0

            for _, rel_path, frontmatter, _ in all_pages:
                title = frontmatter.get("title", "").lower()
                score = 0
                if link_text in title:
                    score = len(link_text)
                if rel_path.lower() in link_text or link_text in rel_path.lower():
                    score += 5

                if score > highest_score:
                    highest_score = score
                    best_match = rel_path

            if best_match and highest_score >= 3:
                # 找到匹配的页面，更新链接
                page_path = settings.wiki_dir / link["page"]
                content = page_path.read_text(encoding="utf-8")
                old_link = f"[{link['link_text']}]({link['target']})"
                new_link = f"[{link['link_text']}]({best_match})"
                content = content.replace(old_link, new_link)
                page_path.write_text(content, encoding="utf-8")
                fixed_count += 1
                if link["page"] not in changed_files:
                    changed_files.append(link["page"])

    # 修复缺失页面：创建简单的占位页面
    if "missing_page" in fix_types:
        missing_pages = [i for i in issues if i["type"] == "missing_page"]
        for missing in missing_pages:
            concept = missing["target"]
            # 生成页面路径
            slug = generate_slug(concept)
            page_path = settings.wiki_dir / "concepts" / f"{slug}.md"
            rel_path = f"concepts/{slug}.md"

            if not page_path.exists() and rel_path not in all_page_paths:
                # 创建页面
                frontmatter = {
                    "title": concept,
                    "type": "concept",
                    "tags": [],
                    "created_at": get_date_prefix(),
                    "updated_at": get_date_prefix(),
                    "source_count": 0
                }
                content = build_frontmatter(frontmatter) + f"\n# {concept}\n\nTODO: 请补充{concept}的详细内容。\n"
                page_path.parent.mkdir(exist_ok=True, parents=True)
                page_path.write_text(content, encoding="utf-8")
                fixed_count += 1
                changed_files.append(rel_path)

                # 更新索引
                update_index(page_path, concept, "concept")
                if "wiki/index.md" not in changed_files:
                    changed_files.append("wiki/index.md")

    return {
        "fixed_count": fixed_count,
        "changed_files": changed_files
    }
