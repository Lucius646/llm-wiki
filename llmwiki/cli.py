import os
import sys
from pathlib import Path
from datetime import datetime
import click
from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status

# 修复Windows中文编码问题
os.environ['LC_ALL'] = 'en_US.UTF-8'
os.environ['LANG'] = 'en_US.UTF-8'
os.environ['PYTHONIOENCODING'] = 'utf-8'

# Load .env file
load_dotenv()

from llmwiki import __version__
from llmwiki.config import settings
from llmwiki.ingest import ingest_source
from llmwiki.query import query_wiki
from llmwiki.lint import lint_wiki
from llmwiki.utils import init_wiki_structure, get_wiki_status, get_operation_log

# 初始化Rich控制台
console = Console()

# 全局键绑定
kb = KeyBindings()

@kb.add('c-c')
def _(event):
    "Ctrl+C退出"
    event.app.exit()

@kb.add('c-d')
def _(event):
    "Ctrl+D退出"
    event.app.exit()

@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.option("--wiki-root", type=click.Path(exists=True, file_okay=False, path_type=Path),
              help="Root directory of the wiki (default: current directory)")
@click.pass_context
def cli(ctx: click.Context, wiki_root: Path | None):
    """LLM Wiki: A lightweight CLI tool for building and maintaining LLM-powered knowledge bases."""
    if wiki_root:
        # Override settings wiki root
        os.environ["WIKI_ROOT"] = str(wiki_root)
        # Reload settings
        from importlib import reload
        from llmwiki import config
        reload(config)
        global settings
        settings = config.settings
    ctx.ensure_object(dict)

    # Default to chat mode when no subcommand is given
    if ctx.invoked_subcommand is None:
        # Call chat command with default parameters
        ctx.invoke(chat, persist=None, no_history=False)

@cli.command(name="login")
@click.option("--provider", type=click.Choice(["openai", "anthropic"]), default="openai",
              help="LLM provider to login to (default: openai)")
def login(provider: str):
    """Login to LLM provider using official OAuth flow (no manual API key required)."""
    if provider == "openai":
        from llmwiki.auth import start_openai_device_flow
        success = start_openai_device_flow()
        sys.exit(0 if success else 1)
    elif provider == "anthropic":
        # Anthropic doesn't support OAuth yet, prompt for API key
        click.echo("🔐 Anthropic 授权登录")
        api_key = click.prompt("请输入你的Anthropic API Key", hide_input=True)
        if api_key.strip():
            from llmwiki.config import UserConfig
            UserConfig.save_anthropic_key(api_key.strip())
            click.echo("✅ Anthropic API Key 已保存！")
            sys.exit(0)
        else:
            click.echo("❌ API Key 不能为空", err=True)
            sys.exit(1)

@cli.command()
@click.option("--force", is_flag=True, help="Force initialization even if directories already exist")
def init(force: bool):
    """Initialize a new LLM Wiki directory structure."""
    click.echo("Initializing LLM Wiki...")
    try:
        init_wiki_structure(force=force)
        click.echo("✅ Wiki initialized successfully!")
        click.echo("\nNext steps:")
        click.echo("1. Add your API keys to .env file")
        click.echo("2. Run `llmwiki ingest <path/to/your/file>` to add your first source")
    except Exception as e:
        click.echo(f"❌ Error initializing wiki: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.argument("path")
@click.option("--topic", help="Topic category for the source (auto-detected if not provided)")
@click.option("--auto-approve", is_flag=True, help="Auto-approve changes without confirmation")
def ingest(path: str, topic: str | None, auto_approve: bool):
    """Ingest a source file or URL into the wiki."""
    click.echo(f"🔍 Ingesting source: {path}")
    try:
        result = ingest_source(path, topic=topic, auto_approve=auto_approve)
        if result:
            click.echo(f"✅ Successfully ingested source!")
            click.echo(f"  Created/Updated {result.get('changed_pages', 0)} pages")
            if result.get('new_pages'):
                click.echo("  New pages:")
                for page in result['new_pages']:
                    click.echo(f"    - {page}")
        else:
            click.echo("❌ Ingestion failed")
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Error ingesting source: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.argument("question")
@click.option("--save", is_flag=True, help="Save the answer as a new synthesis page")
@click.option("--topic", help="Topic category for the saved page")
@click.option("--no-semantic", is_flag=True, help="Disable semantic search, use keyword search only")
def query(question: str, save: bool, topic: str | None, no_semantic: bool):
    """Query the wiki and get cited answers."""
    click.echo(f"🔍 Querying: {question}")
    try:
        answer = query_wiki(question, save=save, topic=topic, use_semantic=not no_semantic)
        click.echo("\n📝 Answer:")
        click.echo(answer)
        if save:
            click.echo("\n✅ Answer saved as a new synthesis page!")
    except Exception as e:
        click.echo(f"❌ Error querying wiki: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option("--auto-fix", is_flag=True, help="Auto-fix repairable issues")
@click.option("--report", is_flag=True, default=True, help="Generate a check report")
def lint(auto_fix: bool, report: bool):
    """Run health check on the wiki."""
    click.echo("🔍 Running wiki health check...")
    try:
        result = lint_wiki(auto_fix=auto_fix, generate_report=report)
        if report:
            click.echo("\n📋 Lint Report:")
            click.echo(result['report'])

        click.echo(f"\nFound {result['total_issues']} issues, {result['fixed_issues']} auto-fixed")

        if result['total_issues'] > 0 and not auto_fix:
            click.echo("\n💡 Run `llmwiki lint --auto-fix` to fix repairable issues")
    except Exception as e:
        click.echo(f"❌ Error running lint: {e}", err=True)
        sys.exit(1)

@cli.command()
def status():
    """Show current wiki status."""
    try:
        status_info = get_wiki_status()
        click.echo("📊 Wiki Status:")
        click.echo(f"  Total pages: {status_info['total_pages']}")
        click.echo(f"  Concepts: {status_info['concept_count']}")
        click.echo(f"  Entities: {status_info['entity_count']}")
        click.echo(f"  Sources: {status_info['source_count']}")
        click.echo(f"  Synthesis: {status_info['synthesis_count']}")
        click.echo(f"  Last updated: {status_info['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        click.echo(f"❌ Error getting status: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.option("--limit", type=int, default=10, help="Number of log entries to show (default: 10)")
def log(limit: int):
    """Show recent operation logs."""
    try:
        logs = get_operation_log(limit=limit)
        click.echo(f"📋 Last {limit} operations:")
        for entry in logs:
            click.echo(f"\n{entry['timestamp']} {entry['type']} | {entry['description']}")
            if entry.get('details'):
                for detail in entry['details']:
                    click.echo(f"  - {detail}")
    except Exception as e:
        click.echo(f"❌ Error getting logs: {e}", err=True)
        sys.exit(1)

@cli.command()
@click.argument("keyword")
@click.option("--limit", type=int, default=10, help="Maximum number of results (default: 10)")
def search(keyword: str, limit: int):
    """Search wiki content for keywords."""
    from llmwiki.search import search_wiki
    try:
        results = search_wiki(keyword, limit=limit)
        click.echo(f"🔍 Search results for '{keyword}':")
        if not results:
            click.echo("  No results found")
            return

        for i, result in enumerate(results, 1):
            click.echo(f"\n{i}. {result['title']} ({result['path']})")
            click.echo(f"   Score: {result['score']:.2f}")
            click.echo(f"   Preview: {result['preview']}")
    except Exception as e:
        click.echo(f"❌ Error searching wiki: {e}", err=True)
        sys.exit(1)

@cli.command(name="chat")
@click.option("--persist", type=str, default=None, help="持久化会话到指定Markdown文件")
@click.option("--no-history", is_flag=True, default=False, help="不保存输入历史")
def chat(persist, no_history):
    """进入交互式聊天会话，和知识库对话（Claude Code风格）"""
    # 准备历史记录目录
    history_file = None
    if not no_history:
        history_dir = Path.home() / ".llm-wiki"
        history_dir.mkdir(exist_ok=True)
        history_file = history_dir / "chat_history.txt"

    # 创建Prompt会话
    session = PromptSession(
        history=FileHistory(history_file) if history_file else None,
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=kb,
        message="> "
    )

    # 启动欢迎界面
    console.print(Panel.fit(
        f"[bold blue]🧠 LLM Wiki v{__version__} 交互式会话[/bold blue]\n"
        "输入问题直接查询知识库，支持Markdown输出\n"
        "内置命令：/help 查看帮助 | /provider 查看模型接入指南 | /ingest 摄入文件 | /status 查看状态 | /exit 退出\n"
        "快捷键：Ctrl+C/Ctrl+D 退出 | 上下键翻历史输入",
        border_style="blue"
    ))
    console.print()

    # 检查LLM配置状态，提示引导
    from llmwiki.config import UserConfig
    has_creds = UserConfig.get_active_llm_credentials() is not None
    if not has_creds:
        console.print(Panel(
            "⚠️  [bold yellow]未检测到有效的LLM凭证[/bold yellow]\n\n"
            "你可以选择以下方式配置：\n"
            "1. 🔑 运行 [bold]llmwiki login[/bold] 登录OpenAI官方账号（无需API密钥）\n"
            "2. 🔌 输入 [bold]/provider[/bold] 查看自定义LLM接入指南（支持本地开源模型/第三方接口）\n"
            "3. ⚙️  在.env文件中配置API_KEY\n\n"
            "目前处于模拟模式，仅返回知识库原始内容，不会调用LLM生成回答",
            border_style="yellow"
        ))
        console.print()

    # 上下文记忆
    context = []

    # REPL主循环
    while True:
        try:
            user_input = session.prompt()
        except (EOFError, KeyboardInterrupt):
            console.print("\n👋 会话结束", style="dim")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # 处理内置命令
        if user_input.startswith("/"):
            cmd = user_input[1:].strip().lower()
            if cmd in ["exit", "quit", "q"]:
                console.print("👋 会话结束", style="dim")
                break
            elif cmd == "help":
                console.print(Panel(
                    "📖 [bold]帮助说明[/bold]\n"
                    "- 直接输入问题查询知识库\n"
                    "- /ingest <文件路径/URL> [--topic 分类]：摄入新资料\n"
                    "- /status：查看知识库状态\n"
                    "- /provider：查看自定义LLM模型接入指南\n"
                    "- /lint [--auto-fix]：运行健康检查\n"
                    "- /save [文件名]：保存当前会话到synthesis页面\n"
                    "- /clear：清空当前上下文\n"
                    "- /exit /q：退出会话",
                    border_style="green"
                ))
                continue
            elif cmd == "provider" or cmd == "providers":
                console.print(Panel(
                    "🔌 [bold]自定义LLM模型接入指南[/bold]\n\n"
                    "[bold yellow]方法1: 使用内置支持的第三方Provider[/bold yellow]\n"
                    "• Ollama (本地开源大模型): LLM_PROVIDER=ollama\n"
                    "• OpenRouter (多模型网关): LLM_PROVIDER=openrouter\n\n"
                    "[bold yellow]方法2: 快速添加自定义Provider[/bold yellow]\n"
                    "1. 在项目中创建自定义Provider类，继承BaseLLMProvider\n"
                    "2. 实现chat_completion方法调用你的LLM接口\n"
                    "3. 调用register_provider('your_provider', YourProvider)注册\n\n"
                    "[bold yellow]配置示例 (.env 文件):[/bold yellow]\n"
                    "```env\n"
                    "LLM_PROVIDER=ollama\n"
                    "MODEL_NAME=llama3:8b\n"
                    "CUSTOM_PROVIDER_CONFIGS='{\"ollama\": {\"base_url\": \"http://localhost:11434/api\"}}'\n"
                    "```\n\n"
                    "[bold yellow]完整示例代码:[/bold yellow]\n"
                    "查看 examples/custom_provider_example.py 包含Ollama和OpenRouter的完整实现\n\n"
                    "[bold blue]💡 提示:[/bold blue] 当前配置的Provider是 [bold]{settings.llm_provider}[/bold]，使用模型 [bold]{settings.model_name}[/bold]",
                    border_style="magenta",
                    width=90
                ))
                continue
            elif cmd == "clear":
                context = []
                console.print("✅ 上下文已清空", style="green")
                continue
            elif cmd.startswith("ingest"):
                # 解析ingest命令参数，调用ingest_source
                parts = cmd.split()
                if len(parts) < 2:
                    console.print("❌ 请指定文件路径：/ingest <文件路径>", style="red")
                    continue
                path = parts[1]
                topic = parts[3] if len(parts) >=4 and parts[2] == "--topic" else None
                with Status(f"正在摄入 {path}...", spinner="dots"):
                    try:
                        result = ingest_source(path, topic=topic, auto_approve=True)
                        console.print(f"✅ 成功摄入，变更 {result.get('changed_pages',0)} 个页面", style="green")
                    except Exception as e:
                        console.print(f"❌ 摄入失败：{str(e)}", style="red")
                continue
            elif cmd == "status":
                status = get_wiki_status()
                console.print(Panel(
                    f"📊 [bold]知识库状态[/bold]\n"
                    f"总页面数：{status['total_pages']}\n"
                    f"概念：{status['concept_count']} | 实体：{status['entity_count']}\n"
                    f"来源：{status['source_count']} | 综合分析：{status['synthesis_count']}\n"
                    f"最后更新：{status['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}",
                    border_style="cyan"
                ))
                continue
            elif cmd.startswith("save"):
                # 保存会话逻辑后面完善
                console.print("✅ 会话保存功能即将上线", style="dim")
                continue
            else:
                console.print(f"❌ 未知命令：{cmd}，输入/help查看帮助", style="red")
                continue

        # 处理普通提问，调用query_wiki
        with Status("正在查询知识库...", spinner="dots"):
            try:
                answer = query_wiki(user_input, save=False, context=context)
                # 渲染Markdown回答
                console.print()
                console.print(Panel(
                    Markdown(answer),
                    title="🤖 回答",
                    border_style="green",
                    title_align="left"
                ))
                console.print()
                # 加入上下文
                context.append({"role": "user", "content": user_input})
                context.append({"role": "assistant", "content": answer})
                # 上下文长度管理：最多保留最近10轮对话（20条消息）
                if len(context) > 20:
                    # 删除最早的2条（一轮对话）
                    context = context[2:]
            except Exception as e:
                console.print(f"❌ 查询失败：{str(e)}", style="red")
                continue

# 向量检索相关命令
@cli.group(name="vector")
def vector():
    """离线向量检索相关操作."""
    pass

@vector.command(name="build")
@click.option("--force", is_flag=True, help="Force rebuild the entire index, not just incremental update")
def vector_build(force: bool):
    """Build or update the vector index for semantic search."""
    try:
        from llmwiki.vector_search import VectorIndex, VECTOR_SUPPORT
        if not VECTOR_SUPPORT:
            click.echo("❌ 向量检索功能需要安装依赖：pip install sentence-transformers numpy scikit-learn", err=True)
            sys.exit(1)

        click.echo("🔄 正在构建向量索引（首次运行会自动下载模型，大约需要几分钟）...")
        index = VectorIndex()
        index.build_index(force_rebuild=force)
        click.echo(f"✅ 向量索引构建完成！共索引 {len(index.vectors)} 个页面")
    except Exception as e:
        click.echo(f"❌ 构建向量索引失败：{e}", err=True)
        sys.exit(1)

@vector.command(name="search")
@click.argument("query")
@click.option("--limit", type=int, default=5, help="Maximum number of results (default: 5)")
@click.option("--min-score", type=float, default=0.3, help="Minimum similarity score (0-1, default: 0.3)")
def vector_search(query: str, limit: int, min_score: float):
    """Semantic search wiki content by meaning, not just keywords."""
    try:
        from llmwiki.vector_search import VectorIndex, VECTOR_SUPPORT
        if not VECTOR_SUPPORT:
            click.echo("❌ 向量检索功能需要安装依赖：pip install sentence-transformers numpy scikit-learn", err=True)
            sys.exit(1)

        click.echo(f"🔍 语义搜索: {query}")
        index = VectorIndex()
        index.load_index()
        # 如果索引不存在，自动构建
        if not index.vectors:
            click.echo("⚠️ 未找到向量索引，正在自动构建...")
            index.build_index()

        results = index.search(query, top_k=limit, min_score=min_score)
        if not results:
            click.echo("  没有找到相关结果")
            return

        for i, result in enumerate(results, 1):
            click.echo(f"\n{i}. {result['title']} ({result['path']})")
            click.echo(f"   相似度: {result['score']:.2f}")
            # 显示预览
            file_path = settings.wiki_dir / result["path"]
            content = file_path.read_text(encoding="utf-8")
            from llmwiki.utils import extract_frontmatter
            _, body = extract_frontmatter(content)
            preview = body[:150].replace("\n", " ").strip()
            if len(preview) > 150:
                preview = preview[:147] + "..."
            click.echo(f"   预览: {preview}")
    except Exception as e:
        click.echo(f"❌ 语义搜索失败：{e}", err=True)
        sys.exit(1)

@vector.command(name="status")
def vector_status():
    """Show vector index status."""
    try:
        from llmwiki.vector_search import VectorIndex, VECTOR_SUPPORT
        if not VECTOR_SUPPORT:
            click.echo("❌ 向量检索功能需要安装依赖：pip install sentence-transformers numpy scikit-learn", err=True)
            sys.exit(1)

        index = VectorIndex()
        if not index.index_path.exists():
            click.echo("⚠️ 向量索引尚未构建，请先运行 `llmwiki vector build`")
            return

        index.load_index()
        # 统计信息
        total_pages = len(index.vectors)
        last_modified = datetime.fromtimestamp(index.index_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        index_size = f"{index.index_path.stat().st_size / 1024 / 1024:.2f} MB" if index.index_path.stat().st_size > 1024 * 1024 else f"{index.index_path.stat().st_size / 1024:.2f} KB"

        click.echo("📊 向量索引状态:")
        click.echo(f"  已索引页面数: {total_pages}")
        click.echo(f"  最后更新时间: {last_modified}")
        click.echo(f"  索引文件大小: {index_size}")
        click.echo(f"  索引文件路径: {index.index_path}")
    except Exception as e:
        click.echo(f"❌ 获取索引状态失败：{e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    cli()
