from setuptools import setup, find_packages

setup(
    name="llmwiki",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "llmwiki = llmwiki.cli:cli",
        ],
    },
    install_requires=[
        "click>=8.0",
        "openai>=1.0",
        "anthropic>=0.20",
        "pydantic>=2.0",
        "python-dotenv>=1.0",
        "PyPDF2>=3.0",
        "python-docx>=1.1",
        "requests>=2.31",
        "beautifulsoup4>=4.12",
        "openai-whisper>=20231117",
        "whoosh>=2.7.4",
        "GitPython>=3.1",
        "python-slugify>=8.0",
        "markdown>=3.5",
        "python-dateutil>=2.8"
    ],
    author="Lucius",
    description="A lightweight CLI tool for building and maintaining LLM-powered knowledge bases",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/llmwiki",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
