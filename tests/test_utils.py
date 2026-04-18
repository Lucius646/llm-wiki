import os
import tempfile
from pathlib import Path
from llmwiki.utils import (
    generate_slug,
    get_date_prefix,
    extract_frontmatter,
    build_frontmatter,
    init_wiki_structure
)

def test_generate_slug():
    """测试slug生成"""
    # 中文标题
    assert generate_slug("这是测试标题", max_length=20) == "这是测试标题"
    # 英文标题转小写，空格变-
    assert generate_slug("Hello World Test", max_length=20) == "hello-world-test"
    # 特殊字符过滤
    assert generate_slug("Hello!@#$%^&*()World") == "helloworld"
    # 长度截断
    assert generate_slug("a"*30, max_length=10) == "a"*10

def test_get_date_prefix():
    """测试日期前缀生成"""
    import re
    date_pattern = r"^\d{4}-\d{2}-\d{2}$"
    assert re.match(date_pattern, get_date_prefix()) is not None

def test_build_and_extract_frontmatter():
    """测试frontmatter构建和解析"""
    # 基础测试
    data = {
        "title": "测试标题",
        "type": "concept",
        "tags": ["tag1", "tag2", "中文标签"],
        "created_at": "2024-04-18",
        "source_count": 3
    }

    fm_str = build_frontmatter(data)
    # 验证格式正确
    assert fm_str.startswith("---\n")
    assert fm_str.endswith("---\n")

    # 解析回来
    parsed, body = extract_frontmatter(fm_str + "\n正文内容\n")
    assert parsed == data
    assert body == "正文内容"

def test_extract_frontmatter_no_header():
    """测试没有frontmatter的情况"""
    content = "纯正文内容\n没有frontmatter"
    parsed, body = extract_frontmatter(content)
    assert parsed == {}
    assert body == content

def test_init_wiki_structure():
    """测试wiki目录初始化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        # 设置环境变量覆盖wiki根目录
        os.environ["WIKI_ROOT"] = tmpdir

        # 执行初始化
        init_wiki_structure(force=True)

        # 验证目录结构
        assert Path("raw/assets").exists()
        assert Path("raw/articles").exists()
        assert Path("raw/papers").exists()
        assert Path("raw/notes").exists()
        assert Path("raw/books").exists()

        assert Path("wiki/concepts").exists()
        assert Path("wiki/entities").exists()
        assert Path("wiki/sources").exists()
        assert Path("wiki/synthesis").exists()

        # 验证文件存在
        assert Path("wiki/index.md").exists()
        assert Path("wiki/log.md").exists()

        # 验证index内容
        index_content = Path("wiki/index.md").read_text()
        assert "# Wiki Index" in index_content
        assert "## Concepts" in index_content
        assert "## Entities" in index_content
        assert "## Sources" in index_content
        assert "## Synthesis" in index_content
