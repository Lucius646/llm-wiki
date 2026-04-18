from pathlib import Path
from git import Repo, GitCommandError
from typing import List, Optional
from llmwiki.config import settings

def get_repo() -> Optional[Repo]:
    """Get the Git repository instance"""
    try:
        return Repo(settings.wiki_root)
    except:
        return None

def is_repo_initialized() -> bool:
    """Check if Git repository is initialized"""
    return get_repo() is not None

def commit_changes(message: str, files: List[str | Path] | None = None) -> Optional[str]:
    """
    Commit changes to Git repository

    Args:
        message: Commit message
        files: List of files to commit (all changes if None)

    Returns:
        提交成功返回新的commit哈希，失败返回None
    """
    if not settings.git_auto_commit:
        return None

    repo = get_repo()
    if not repo:
        return None

    try:
        if files:
            # Commit only specified files
            file_paths = []
            for f in files:
                p = Path(f)
                if not p.is_absolute():
                    # 如果是相对路径，假设是相对wiki目录的，转换为绝对路径
                    p = settings.wiki_dir / p
                file_paths.append(str(p.absolute()))
            repo.index.add(file_paths)
        else:
            # Commit all changes
            repo.git.add(A=True)

        if repo.is_dirty():
            commit = repo.index.commit(message + "\n\nCo-Authored-by: LLM Wiki <llmwiki@example.com>")
            return commit.hexsha
        return None
    except GitCommandError as e:
        print(f"Git commit error: {e}")
        return None
