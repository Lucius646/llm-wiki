import os
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
from llmwiki.config import settings
from llmwiki.git_utils import commit_changes

def _run_git_command(cmd: str, cwd: Optional[str] = None) -> str:
    """运行Git命令，返回输出结果"""
    if cwd is None:
        cwd = str(settings.wiki_root)
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""

def get_page_history(page_path: str) -> List[Dict[str, Any]]:
    """
    获取页面的历史版本列表

    Args:
        page_path: 页面的相对路径，比如"concepts/rag.md"

    Returns:
        版本列表，按时间倒序排列，每个版本包含hash、author、date、message字段
    """
    full_path = settings.wiki_dir / page_path
    if not full_path.exists():
        return []

    # 运行git log命令获取该文件的提交历史
    git_cmd = f'git log --pretty=format:"%H|%an|%ad|%s" --date=iso -- "{full_path}"'
    output = _run_git_command(git_cmd)

    history = []
    for line in output.split("\n"):
        if not line:
            continue
        parts = line.split("|")
        if len(parts) != 4:
            continue
        commit_hash, author, date_str, message = parts
        # 解析日期
        try:
            date = datetime.fromisoformat(date_str.strip())
        except ValueError:
            date = datetime.now()

        history.append({
            "hash": commit_hash.strip(),
            "author": author.strip(),
            "date": date,
            "message": message.strip()
        })

    return history

def get_version_content(page_path: str, commit_hash: str) -> Optional[str]:
    """
    获取页面某个历史版本的内容

    Args:
        page_path: 页面相对路径
        commit_hash: 提交哈希

    Returns:
        版本内容，如果版本不存在返回None
    """
    full_path = settings.wiki_dir / page_path
    if not full_path.exists():
        return None

    # 运行git show命令获取指定版本的文件内容，Windows下路径用正斜杠
    rel_path = str(full_path.relative_to(settings.wiki_root)).replace("\\", "/")
    git_cmd = f'git show {commit_hash}:{rel_path}'
    content = _run_git_command(git_cmd)

    return content if content else None

def diff_versions(page_path: str, old_hash: str, new_hash: str) -> Dict[str, Any]:
    """
    对比页面两个版本之间的差异

    Args:
        page_path: 页面相对路径
        old_hash: 旧版本哈希
        new_hash: 新版本哈希

    Returns:
        差异结果，包含added、removed、modified列表和diff_text完整差异文本
    """
    full_path = settings.wiki_dir / page_path
    if not full_path.exists():
        return {"added": [], "removed": [], "modified": [], "diff_text": ""}

    # 运行git diff命令获取两个版本的差异，Windows下路径用正斜杠
    rel_path = str(full_path.relative_to(settings.wiki_root)).replace("\\", "/")
    git_cmd = f'git diff {old_hash} {new_hash} -- {rel_path}'
    diff_text = _run_git_command(git_cmd)

    added = []
    removed = []
    modified = []

    # 解析差异内容
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:].strip())
        elif line.startswith("-") and not line.startswith("---"):
            removed.append(line[1:].strip())
        elif line.startswith("@@"):
            # 行号信息，忽略
            continue

    # 检查frontmatter修改
    frontmatter_modified = False
    if "---" in diff_text:
        frontmatter_lines = [l for l in diff_text.split("\n") if l.startswith(("+tags:", "-tags:", "+updated_at:", "-updated_at:", "+source_count:", "-source_count:"))]
        modified.extend([l[1:].strip() for l in frontmatter_lines])

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "diff_text": diff_text
    }

def restore_version(page_path: str, commit_hash: str, commit_message: Optional[str] = None) -> Dict[str, Any]:
    """
    恢复页面到指定历史版本

    Args:
        page_path: 页面相对路径
        commit_hash: 要恢复到的版本哈希
        commit_message: 可选的提交信息，默认自动生成

    Returns:
        恢复结果，包含success、old_version、new_version字段
    """
    full_path = settings.wiki_dir / page_path
    if not full_path.exists():
        return {"success": False, "error": "页面不存在"}

    # 先获取当前版本的哈希
    current_hash = _run_git_command('git rev-parse HEAD')

    # 获取要恢复的版本内容
    version_content = get_version_content(page_path, commit_hash)
    if version_content is None:
        return {"success": False, "error": "无效的版本哈希"}

    try:
        # 写入内容到文件
        full_path.write_text(version_content, encoding="utf-8")

        # 提交变更
        if not commit_message:
            commit_message = f"revert: 恢复页面到版本 {commit_hash[:7]}"

        new_commit_hash = commit_changes(commit_message, [page_path])

        return {
            "success": True,
            "old_version": current_hash,
            "restored_version": commit_hash,
            "new_version": new_commit_hash,
            "message": commit_message
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_recent_changes(days: int = 7) -> List[Dict[str, Any]]:
    """
    获取最近一段时间的所有变更

    Args:
        days: 最近多少天的变更，默认7天

    Returns:
        变更列表，包含commit信息和变更的文件
    """
    git_cmd = f'git log --since="{days} days ago" --pretty=format:"%H|%an|%ad|%s" --date=iso --name-only'
    output = _run_git_command(git_cmd)

    changes = []
    current_commit = None

    for line in output.split("\n"):
        if not line:
            if current_commit:
                changes.append(current_commit)
                current_commit = None
            continue

        if "|" in line:
            parts = line.split("|")
            if len(parts) == 4:
                commit_hash, author, date_str, message = parts
                try:
                    date = datetime.fromisoformat(date_str.strip())
                except ValueError:
                    date = datetime.now()

                current_commit = {
                    "hash": commit_hash.strip(),
                    "author": author.strip(),
                    "date": date,
                    "message": message.strip(),
                    "files": []
                }
        elif current_commit is not None and line.strip():
            # 文件路径
            current_commit["files"].append(line.strip())

    if current_commit:
        changes.append(current_commit)

    return changes
