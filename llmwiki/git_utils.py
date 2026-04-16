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

def commit_changes(message: str, files: List[str | Path] | None = None) -> bool:
    """
    Commit changes to Git repository

    Args:
        message: Commit message
        files: List of files to commit (all changes if None)

    Returns:
        True if commit was successful, False otherwise
    """
    if not settings.git_auto_commit:
        return False

    repo = get_repo()
    if not repo:
        return False

    try:
        if files:
            # Commit only specified files
            file_paths = [str(Path(f).absolute()) for f in files]
            repo.index.add(file_paths)
        else:
            # Commit all changes
            repo.git.add(A=True)

        if repo.is_dirty():
            repo.index.commit(message + "\n\nCo-Authored-by: LLM Wiki <llmwiki@example.com>")
            return True
        return False
    except GitCommandError as e:
        print(f"Git commit error: {e}")
        return False
