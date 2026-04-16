import os
import sys
from pathlib import Path
from datetime import datetime
import click
from dotenv import load_dotenv

# Load .env file
load_dotenv()

from llmwiki import __version__
from llmwiki.config import settings
from llmwiki.ingest import ingest_source
from llmwiki.query import query_wiki
from llmwiki.lint import lint_wiki
from llmwiki.utils import init_wiki_structure, get_wiki_status, get_operation_log

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

if __name__ == "__main__":
    cli()
