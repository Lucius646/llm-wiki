import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure, build_frontmatter
from llmwiki.version_history import get_page_history, get_version_content, diff_versions, restore_version
from llmwiki.git_utils import commit_changes

def setup_module(module):
    """Setup test environment before all tests"""
    # Create temporary directory for test wiki
    module.tmp_dir = tempfile.TemporaryDirectory()
    module.original_wiki_root = settings.wiki_root
    # Only set wiki_root, other paths are computed properties
    object.__setattr__(settings, 'wiki_root', Path(module.tmp_dir.name))

    # Initialize wiki structure
    init_wiki_structure(force=True)

    # Initialize git repo in the temp directory
    os.chdir(module.tmp_dir.name)
    os.system("git init")
    os.system('git config user.name "Test User"')
    os.system('git config user.email "test@example.com"')

    # Create test page with multiple versions
    module.test_page_path = settings.wiki_dir / "concepts/test-page.md"
    module.test_page_rel_path = "concepts/test-page.md"

    # Version 1: Initial content
    v1_content = build_frontmatter({
        "title": "测试页面",
        "type": "concept",
        "tags": ["测试"],
        "created_at": "2024-04-17",
        "updated_at": "2024-04-17",
        "source_count": 0
    }) + "\n# 测试页面\n\n这是测试页面的初始版本。\n初始内容行。"
    module.test_page_path.write_text(v1_content, encoding="utf-8")
    commit_changes("feat: 添加测试页面v1", [module.test_page_rel_path])
    module.v1_hash = os.popen("git rev-parse HEAD").read().strip()

    # Version 2: Add more content
    v2_content = build_frontmatter({
        "title": "测试页面",
        "type": "concept",
        "tags": ["测试", "版本2"],
        "created_at": "2024-04-17",
        "updated_at": "2024-04-18",
        "source_count": 0
    }) + "\n# 测试页面\n\n这是测试页面的初始版本。\n初始内容行。\n新增的内容行。\n另一个新增行。"
    module.test_page_path.write_text(v2_content, encoding="utf-8")
    commit_changes("feat: 更新测试页面到v2，添加内容", [module.test_page_rel_path])
    module.v2_hash = os.popen("git rev-parse HEAD").read().strip()

    # Version 3: Modify and delete content
    v3_content = build_frontmatter({
        "title": "测试页面",
        "type": "concept",
        "tags": ["测试", "版本3"],
        "created_at": "2024-04-17",
        "updated_at": "2024-04-19",
        "source_count": 1
    }) + "\n# 测试页面\n\n这是测试页面的第三个版本。\n修改了第一行内容。\n新增的内容行。"
    module.test_page_path.write_text(v3_content, encoding="utf-8")
    commit_changes("feat: 更新测试页面到v3，修改内容", [module.test_page_rel_path])
    module.v3_hash = os.popen("git rev-parse HEAD").read().strip()

def teardown_module(module):
    """Cleanup test environment after all tests"""
    os.chdir(Path(__file__).parent.parent)
    try:
        module.tmp_dir.cleanup()
    except:
        pass
    # Restore original wiki_root
    object.__setattr__(settings, 'wiki_root', module.original_wiki_root)

def test_get_page_history():
    """测试获取页面的历史版本列表"""
    history = get_page_history("concepts/test-page.md")
    # 应该有3个版本
    assert len(history) >= 3
    # 按时间倒序排列，最新的在前面
    assert history[0]["message"] == "feat: 更新测试页面到v3，修改内容"
    assert history[1]["message"] == "feat: 更新测试页面到v2，添加内容"
    assert history[2]["message"] == "feat: 添加测试页面v1"
    # 每个版本都包含必要字段
    for version in history:
        assert "hash" in version
        assert "author" in version
        assert "date" in version
        assert "message" in version
        assert isinstance(version["date"], datetime)

def test_get_version_content():
    """测试获取某个历史版本的内容"""
    # 获取v1版本内容
    v1_content = get_version_content("concepts/test-page.md", v1_hash)
    assert "初始版本" in v1_content
    assert "新增的内容行" not in v1_content
    assert "第三个版本" not in v1_content

    # 获取v2版本内容
    v2_content = get_version_content("concepts/test-page.md", v2_hash)
    assert "初始版本" in v2_content
    assert "新增的内容行" in v2_content
    assert "另一个新增行" in v2_content
    assert "第三个版本" not in v2_content

    # 获取v3版本内容
    v3_content = get_version_content("concepts/test-page.md", v3_hash)
    assert "第三个版本" in v3_content
    assert "修改了第一行内容" in v3_content
    assert "另一个新增行" not in v3_content

def test_diff_versions():
    """测试对比两个版本之间的差异"""
    # 对比v1和v2
    diff1 = diff_versions("concepts/test-page.md", v1_hash, v2_hash)
    assert "新增的内容行" in diff1["added"]
    assert "另一个新增行" in diff1["added"]
    assert len(diff1["removed"]) == 0
    assert len(diff1["modified"]) == 0

    # 对比v2和v3
    diff2 = diff_versions("concepts/test-page.md", v2_hash, v3_hash)
    assert "这是测试页面的初始版本" in diff2["removed"]
    assert "初始内容行" in diff2["removed"]
    assert "另一个新增行" in diff2["removed"]
    assert "这是测试页面的第三个版本" in diff2["added"]
    assert "修改了第一行内容" in diff2["added"]
    assert "tags" in diff2["modified"]  # frontmatter里的tags修改了
    assert "updated_at" in diff2["modified"]

    # 差异输出应该是可读的格式
    diff_str = diff2["diff_text"]
    assert "-这是测试页面的初始版本" in diff_str
    assert "+这是测试页面的第三个版本" in diff_str

def test_restore_version():
    """测试恢复页面到历史版本"""
    # 先确认当前内容是v3版本
    current_content = test_page_path.read_text(encoding="utf-8")
    assert "第三个版本" in current_content

    # 恢复到v2版本
    restore_result = restore_version("concepts/test-page.md", v2_hash, commit_message="fix: 恢复页面到v2版本")
    assert restore_result["success"] == True
    assert restore_result["old_version"] == v3_hash
    assert restore_result["new_version"] is not None  # 恢复后会有新的提交

    # 确认内容已经恢复为v2版本
    restored_content = module.test_page_path.read_text(encoding="utf-8")
    assert "这是测试页面的初始版本" in restored_content
    assert "另一个新增行" in restored_content
    assert "第三个版本" not in restored_content

    # 历史记录应该多了一个恢复的提交
    new_history = get_page_history("concepts/test-page.md")
    assert len(new_history) == 4
    assert "恢复页面到v2版本" in new_history[0]["message"]

def test_version_history_for_nonexistent_page():
    """测试获取不存在页面的历史版本"""
    history = get_page_history("concepts/not-exist.md")
    assert history == []

    # 获取不存在版本的内容应该返回None
    content = get_version_content("concepts/test-page.md", "invalid-hash")
    assert content is None
