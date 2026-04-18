from typing import List, Dict, Any
from openai import OpenAI
from anthropic import Anthropic
from llmwiki.config import settings
from llmwiki.utils import extract_frontmatter

class LLMClient:
    def __init__(self):
        self.provider = settings.llm_provider
        self.api_key = settings.api_key
        self.model = settings.model_name

        if self.provider == "openai":
            self.client = OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            self.client = Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def chat_completion(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        Generate a chat completion response

        Args:
            messages: List of message dictionaries with "role" and "content"
            temperature: Sampling temperature

        Returns:
            Generated response text
        """
        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=4096
            )
            return response.content[0].text

# Global client instance
_client = None

def get_llm_client() -> LLMClient:
    """Get the global LLM client instance"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

def analyze_content(content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze content to extract concepts, entities, key points

    Args:
        content: Source content text
        metadata: Source metadata

    Returns:
        Analysis result with concepts, entities, summary, key points
    """
    # TODO: Implement content analysis logic
    print("DEBUG: Analyzing content with LLM")

    client = get_llm_client()
    prompt = f"""
    Analyze the following content and extract information:

    Title: {metadata.get('title', 'Unknown')}
    Author: {metadata.get('author', 'Unknown')}
    Published Date: {metadata.get('published_date', 'Unknown')}

    Content:
    {content[:8000]}  # Limit content length

    Please respond with a JSON object containing:
    1. "summary": A concise 2-3 sentence summary of the content
    2. "key_points": List of key takeaways (max 10 points)
    3. "concepts": List of important concepts, terms, technologies mentioned
    4. "entities": List of people, organizations, products, projects mentioned
    5. "topic": The main topic category of this content
    """

    messages = [
        {"role": "system", "content": "You are an expert knowledge base curator. Extract structured information from content accurately."},
        {"role": "user", "content": prompt}
    ]

    response = client.chat_completion(messages, temperature=0.3)
    # TODO: Parse JSON response
    return {
        "summary": "Summary placeholder",
        "key_points": [],
        "concepts": [],
        "entities": [],
        "topic": "uncategorized"
    }

def synthesize_answer(question: str, relevant_pages: List[Dict[str, Any]]) -> str:
    """
    Synthesize an answer to a question based on relevant wiki pages
    Args:
        question: User's question
        relevant_pages: List of relevant pages with content
    Returns:
        Synthesized answer with citations
    """
    if not relevant_pages:
        return "抱歉，没有找到相关的知识库内容。"

    # 测试模式：如果没有配置有效API Key，直接返回模拟回答
    if not settings.api_key or settings.api_key == "your-api-key-here":
        answer = f"根据知识库内容：\n\n"
        for page in relevant_pages:
            answer += f"- {page['title']}：{page['preview']}\n"
        answer += "\n引用来源：\n"
        for page in relevant_pages:
            # 统一使用正斜杠作为路径分隔符
            path = page['path'].replace("\\", "/")
            answer += f"- [{page['title']}]({path})\n"
        return answer

    client = get_llm_client()

    # 构建上下文，限制每个页面的内容长度避免超过token限制
    context = ""
    for i, page in enumerate(relevant_pages):
        frontmatter, body = extract_frontmatter(page["content"])
        # 只保留正文部分，去掉元数据
        context += f"\n=== [{i+1}] {page['title']} (路径: {page['path']}) ===\n"
        context += body[:3000] + "\n"  # 每个页面最多取3000字符

    prompt = f"""
    请根据以下提供的知识库内容，准确回答用户的问题，严格遵守以下规则：

    1. 只能使用提供的上下文内容回答问题，不能编造任何不在上下文里的信息
    2. 所有事实性陈述都必须标注来源，引用格式为：[页面标题](相对路径)
    3. 如果多个来源提到相同内容，可以标注多个来源
    4. 如果上下文里没有足够信息回答问题，直接说："我没有找到相关的信息来回答这个问题。"
    5. 回答结构清晰，逻辑分明，语言简洁明了
    6. 最后可以补充一个"参考资料"部分，列出所有引用的页面

    用户问题：{question}

    知识库内容：
    {context}
    """

    messages = [
        {"role": "system", "content": "你是一个专业的知识库助理，能够准确根据提供的内容回答问题，并且严格标注来源，从不编造信息。"},
        {"role": "user", "content": prompt}
    ]

    try:
        answer = client.chat_completion(messages, temperature=0.3)
        return answer
    except Exception as e:
        return f"生成回答时发生错误：{str(e)}"
