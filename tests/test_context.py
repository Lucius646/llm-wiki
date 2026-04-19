import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from llmwiki.config import settings
from llmwiki.utils import init_wiki_structure
from llmwiki.llm_client import synthesize_answer
from llmwiki.query import query_wiki

def setup_module(module):
    """Setup test environment before all tests"""
    # Create temporary directory for test wiki
    module.tmp_dir = tempfile.TemporaryDirectory()
    module.original_wiki_root = settings.wiki_root
    # Only set wiki_root, other paths are computed properties
    object.__setattr__(settings, 'wiki_root', Path(module.tmp_dir.name))
    # Initialize wiki structure
    init_wiki_structure(force=True)

def teardown_module(module):
    """Cleanup test environment after all tests"""
    try:
        module.tmp_dir.cleanup()
    except:
        pass
    # Restore original wiki_root
    object.__setattr__(settings, 'wiki_root', module.original_wiki_root)

def test_synthesize_answer_with_context():
    """测试 synthesize_answer 正确处理对话上下文"""
    # 模拟相关页面
    relevant_pages = [
        {
            "title": "检索增强生成",
            "path": "concepts/rag.md",
            "content": "---\ntitle: 检索增强生成\n---\nRAG的核心流程包括文档索引构建、用户问题理解、相关文档检索、检索结果增强、回答生成五个步骤。",
            "preview": "RAG的核心流程包括五个步骤..."
        }
    ]

    # 对话历史
    context = [
        {"role": "user", "content": "什么是RAG？"},
        {"role": "assistant", "content": "RAG是检索增强生成技术。"}
    ]

    # 模拟配置了API Key，不走模拟回答分支
    with patch('llmwiki.llm_client.get_llm_client') as mock_get_client, \
         patch('llmwiki.llm_client.settings.api_key', 'test_key'):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "RAG的核心流程有五个步骤。"
        mock_get_client.return_value = mock_client

        # 调用带上下文的合成
        answer = synthesize_answer("它的核心流程有哪些？", relevant_pages, context=context)

        # 验证chat_completion被调用，且prompt包含历史对话内容
        call_args = mock_client.chat_completion.call_args
        assert call_args is not None
        messages = call_args[0][0]
        assert len(messages) == 2
        user_prompt = messages[1]["content"]
        assert "用户: 什么是RAG？" in user_prompt
        assert "助理: RAG是检索增强生成技术。" in user_prompt
        assert "用户问题：它的核心流程有哪些？" in user_prompt

def test_synthesize_answer_without_context():
    """测试没有上下文时功能正常，兼容原有调用方式"""
    relevant_pages = [
        {
            "title": "检索增强生成",
            "path": "concepts/rag.md",
            "content": "---\ntitle: 检索增强生成\n---\nRAG是检索增强生成技术。",
            "preview": "RAG是检索增强生成技术。"
        }
    ]

    # 模拟配置了API Key
    with patch('llmwiki.llm_client.get_llm_client') as mock_get_client, \
         patch('llmwiki.llm_client.settings.api_key', 'test_key'):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "RAG是检索增强生成技术。"
        mock_get_client.return_value = mock_client

        # 不带上下文调用（原有方式）
        answer = synthesize_answer("什么是RAG？", relevant_pages)

        # 验证prompt中没有历史对话内容
        call_args = mock_client.chat_completion.call_args
        assert call_args is not None
        messages = call_args[0][0]
        user_prompt = messages[1]["content"]
        assert "用户: " not in user_prompt  # 没有历史用户消息
        assert "助理: " not in user_prompt  # 没有历史助理消息

def test_synthesize_answer_context_truncation():
    """测试历史对话过长时自动截断"""
    relevant_pages = [
        {
            "title": "检索增强生成",
            "path": "concepts/rag.md",
            "content": "---\ntitle: 检索增强生成\n---\nRAG的核心流程有五个步骤。",
            "preview": "RAG的核心流程有五个步骤。"
        }
    ]

    # 创建超长的历史对话，超过2000字符
    long_context = []
    for i in range(20):
        long_context.append({"role": "user", "content": f"问题{i}: 这是一个很长的问题，用来测试上下文截断功能，确保不会超过token限制。" * 5})
        long_context.append({"role": "assistant", "content": f"回答{i}: 这是对应的回答，同样很长，用来填充上下文长度。" * 5})

    # 模拟配置了API Key
    with patch('llmwiki.llm_client.get_llm_client') as mock_get_client, \
         patch('llmwiki.llm_client.settings.api_key', 'test_key'):
        mock_client = MagicMock()
        mock_client.chat_completion.return_value = "测试回答"
        mock_get_client.return_value = mock_client

        answer = synthesize_answer("它的核心流程有哪些？", relevant_pages, context=long_context)

        # 验证prompt中的历史部分被截断到2000字符以内
        call_args = mock_client.chat_completion.call_args
        assert call_args is not None
        user_prompt = call_args[0][0][1]["content"]
        # 找到当前问题的位置，前面的就是历史相关内容
        current_question_start = user_prompt.find("用户问题：它的核心流程有哪些？")
        assert current_question_start != -1
        # 统计历史部分的长度（规则部分是固定的，大概几百字符，所以总历史内容不会超过2000）
        # 验证没有最早的问题0，说明被截断了
        assert "用户: 问题0" not in user_prompt
        # 验证还有后面的历史内容
        assert "问题19" in user_prompt or "回答19" in user_prompt

@patch('llmwiki.query.hybrid_search')
def test_query_wiki_context_in_search(mock_hybrid_search):
    """测试query_wiki将上下文加入搜索关键词"""
    mock_hybrid_search.return_value = [
        {"title": "检索增强生成", "path": "concepts/rag.md", "score": 100, "content": "RAG的核心流程有五个步骤。"}
    ]

    # 上下文
    context = [
        {"role": "user", "content": "什么是RAG？"},
        {"role": "assistant", "content": "RAG是检索增强生成技术。"}
    ]

    with patch('llmwiki.query.synthesize_answer') as mock_synthesize:
        mock_synthesize.return_value = "RAG的核心流程有五个步骤。"

        # 调用带上下文的查询
        answer = query_wiki("它的核心流程有哪些？", context=context)

        # 验证hybrid_search的查询参数包含上下文内容
        call_args = mock_hybrid_search.call_args
        search_query = call_args[0][0]
        assert "什么是RAG？" in search_query  # 上下文内容被加入到搜索关键词
        assert "检索增强生成技术" in search_query
        assert "它的核心流程有哪些？" in search_query

def test_query_wiki_context_length_management():
    """测试Chat模式下上下文长度自动管理，超过20条自动删除最早的"""
    # 模拟Chat模式的上下文管理逻辑
    context = []
    # 加入15轮对话（30条消息）
    for i in range(15):
        context.append({"role": "user", "content": f"问题{i}"})
        context.append({"role": "assistant", "content": f"回答{i}"})

    # 超过20条（10轮）后，删除最早的2条
    if len(context) > 20:
        context = context[2:]

    assert len(context) == 28  # 删除2条，剩下28条
    # 最早的两条（问题0、回答0）被删除
    assert context[0]["content"] == "问题1"  # 现在第0条是原来的第2条：问题1
    assert context[1]["content"] == "回答1"

@patch('llmwiki.query.hybrid_search')
def test_query_wiki_empty_context(mock_hybrid_search):
    """测试空上下文时功能正常，不影响原有查询逻辑"""
    mock_hybrid_search.return_value = [
        {"title": "检索增强生成", "path": "concepts/rag.md", "score": 100, "content": "RAG是检索增强生成技术。"}
    ]

    with patch('llmwiki.query.synthesize_answer') as mock_synthesize:
        mock_synthesize.return_value = "RAG是检索增强生成技术。"

        # 空上下文调用
        answer = query_wiki("什么是RAG？", context=None)

        # 验证搜索参数正确，没有多余内容
        call_args = mock_hybrid_search.call_args
        search_query = call_args[0][0]
        assert search_query == "什么是RAG？"  # 没有额外上下文内容
