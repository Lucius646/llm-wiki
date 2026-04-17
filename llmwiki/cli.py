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

@click.group()
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
def query(question: str, save: bool, topic: str | None):
    """Query the wiki and get cited answers."""
    click.echo(f"🔍 Querying: {question}")
    try:
        answer = query_wiki(question, save=save, topic=topic)
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
        "内置命令：/help 查看帮助 | /ingest 摄入文件 | /status 查看状态 | /save 保存会话 | /exit 退出\n"
        "快捷键：Ctrl+C/Ctrl+D 退出 | 上下键翻历史输入",
        border_style="blue"
    ))
    console.print()

    # 上下文记忆（暂存，后面完善）
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
                    "- /lint [--auto-fix]：运行健康检查\n"
                    "- /save [文件名]：保存当前会话到synthesis页面\n"
                    "- /clear：清空当前上下文\n"
                    "- /exit /q：退出会话",
                    border_style="green"
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
                answer = query_wiki(user_input, save=False)
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
            except Exception as e:
                console.print(f"❌ 查询失败：{str(e)}", style="red")
                continue

if __name__ == "__main__":
    cli()
