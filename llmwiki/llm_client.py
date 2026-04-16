from typing import List, Dict, Any
from openai import OpenAI
from anthropic import Anthropic
from llmwiki.config import settings

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
    # TODO: Implement answer synthesis logic
    print(f"DEBUG: Synthesizing answer for: {question}")

    client = get_llm_client()

    # Build context from relevant pages
    context = ""
    for i, page in enumerate(relevant_pages):
        context += f"\n=== Page {i+1}: {page['title']} ({page['path']}) ===\n"
        context += page['content'][:3000]  # Limit each page content

    prompt = f"""
    Answer the following question based only on the provided context:

    Question: {question}

    Context:
    {context}

    Instructions:
    1. Answer accurately based only on the information in the context
    2. Cite your sources using markdown links to the page paths, e.g. [Page Title](path/to/page.md)
    3. If the answer is not in the context, say "I don't have enough information to answer this question."
    4. Keep the answer clear and well-structured
    """

    messages = [
        {"role": "system", "content": "You are a helpful assistant that answers questions based only on the provided context, citing sources appropriately."},
        {"role": "user", "content": prompt}
    ]

    return client.chat_completion(messages, temperature=0.5)
