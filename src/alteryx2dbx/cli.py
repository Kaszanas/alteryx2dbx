"""CLI entry point for alteryx2dbx."""

import click
import yaml
from datetime import date
from pathlib import Path
from alteryx2dbx.parser.xml_parser import parse_yxmd
from alteryx2dbx.parser.unpacker import unpack_source
from alteryx2dbx.manifest import serialize_manifest, load_manifest
from alteryx2dbx.starter import write_starter
from alteryx2dbx.generator.notebook import generate_notebooks
from alteryx2dbx.generator.notebook_v2 import generate_notebooks_v2
from alteryx2dbx.generator.batch_report import generate_batch_report
from alteryx2dbx.dag.resolver import resolve_dag
from alteryx2dbx.handlers.registry import get_handler, _registry
import alteryx2dbx.handlers  # noqa: F401  — triggers registration
from alteryx2dbx.document.report import generate_migration_report
from alteryx2dbx.document.portfolio import generate_portfolio_report
from alteryx2dbx.document.config import load_config
from alteryx2dbx.document.confluence import (
    publish_draft,
    confluence_available,
    pat_setup_guide,
)
from alteryx2dbx.lessons.models import Lesson, CATEGORIES
from alteryx2dbx.lessons.store import LessonStore
from alteryx2dbx.plugins.loader import discover_plugins, register_plugins
from alteryx2dbx.fixes import register_fix


def _load_plugins():
    """Discover and register plugins from entry points, config, and local dir."""
    config = {}
    config_path = Path.cwd() / ".alteryx2dbx.yml"
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

    plugins = discover_plugins(config)
    if plugins:
        register_plugins(
            plugins, handler_registry=_registry, fix_registry=register_fix
        )


@click.group()
@click.version_option()
def main():
    """alteryx2dbx -- Convert Alteryx workflows to PySpark Databricks notebooks."""
    pass


@main.command()
@click.option(
    "-o",
    "--output",
    default="./alteryx2dbx_starter.py",
    show_default=True,
    help="Path to write the starter notebook.",
)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite if the file already exists.",
)
def init(output, force):
    """Write a Databricks starter notebook (widgets + install + run) to OUTPUT.

    On Databricks, run this inside a notebook cell with the target path in your
    Workspace, e.g. ``!alteryx2dbx init -o /Workspace/Users/you@company.com/alteryx2dbx_starter.py``.
    Then open the file in the Databricks UI — it's a valid notebook.
    """
    path = Path(output)
    if path.exists() and not force:
        click.echo(
            f"Refusing to overwrite {path}. Pass --force to replace.", err=True
        )
        ctx = click.get_current_context()
        ctx.exit(1)
    written = write_starter(path)
    click.echo(f"Wrote starter notebook: {written}")
    click.echo("Next: open it in Databricks, fill in the widgets, and run.")


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option(
    "-o",
    "--output",
    default="./manifest.json",
    help="Output path (file for single, dir for batch)",
)
def parse(source, output):
    """Parse .yxmd/.yxzp file(s) to JSON manifest(s)."""
    source_path = Path(source)
    output_path = Path(output)

    if source_path.is_file():
        # Single file mode
        unpacked = unpack_source(source_path)
        try:
            wf = parse_yxmd(unpacked.workflow_path)
            # Store macro/asset metadata in properties
            if unpacked.macros:
                wf.properties["macros"] = [str(m.name) for m in unpacked.macros]
            if unpacked.assets:
                wf.properties["assets"] = [str(a.name) for a in unpacked.assets]
            output_path.parent.mkdir(parents=True, exist_ok=True)
            serialize_manifest(wf, output_path)
            click.echo(f"Wrote {output_path}")
        finally:
            unpacked.cleanup()
    else:
        # Batch / directory mode
        files = list(source_path.glob("**/*.yxmd")) + list(
            source_path.glob("**/*.yxzp")
        )
        if not files:
            click.echo("No .yxmd/.yxzp files found.")
            return
        output_path.mkdir(parents=True, exist_ok=True)
        for f in files:
            unpacked = unpack_source(f)
            try:
                wf = parse_yxmd(unpacked.workflow_path)
                if unpacked.macros:
                    wf.properties["macros"] = [
                        str(m.name) for m in unpacked.macros
                    ]
                if unpacked.assets:
                    wf.properties["assets"] = [
                        str(a.name) for a in unpacked.assets
                    ]
                manifest_path = output_path / f"{f.stem}.json"
                serialize_manifest(wf, manifest_path)
                click.echo(f"Wrote {manifest_path}")
            except Exception as e:
                click.echo(f"Error parsing {f.name}: {e}", err=True)
            finally:
                unpacked.cleanup()
        click.echo(f"\nParsed {len(files)} workflow(s).")


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="./output", help="Output directory")
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Generate aggregate batch_report.md",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Use v2 generator (serverless-safe, production notebooks)",
)
def convert(source, output, report, full):
    """Convert .yxmd/.yxzp file(s) to Databricks notebooks."""
    _load_plugins()
    source_path = Path(source)
    output_path = Path(output)
    if source_path.is_file():
        files = [source_path]
    else:
        files = list(source_path.glob("**/*.yxmd")) + list(
            source_path.glob("**/*.yxzp")
        )
    if not files:
        click.echo("No .yxmd or .yxzp files found.")
        return
    results = []
    for f in files:
        click.echo(f"Converting: {f.name}")
        unpacked = unpack_source(f)
        try:
            wf = parse_yxmd(unpacked.workflow_path)
            stats = (
                generate_notebooks_v2(wf, output_path)
                if full
                else generate_notebooks(wf, output_path)
            )
            results.append(stats)
            click.echo(f"  Done: {output_path / wf.name}/")
            for bad in stats.get("syntax_errors", []):
                click.echo(
                    f"  WARN: generated file has syntax error — {bad}", err=True
                )
        except Exception as e:
            click.echo(f"  Error: {e}", err=True)
            results.append(
                {
                    "name": f.stem,
                    "tools_total": 0,
                    "tools_converted": 0,
                    "avg_confidence": 0,
                    "unsupported_tools": [],
                    "errors": [str(e)],
                    "syntax_errors": [],
                }
            )
        finally:
            unpacked.cleanup()
    if report:
        output_path.mkdir(parents=True, exist_ok=True)
        generate_batch_report(output_path, results)
        click.echo(f"Report: {output_path / 'batch_report.md'}")
    total_syntax_errors = sum(len(r.get("syntax_errors", [])) for r in results)
    total_errors = sum(len(r.get("errors", [])) for r in results)
    click.echo(f"\nDone. Converted {len(files)} workflow(s).")
    if total_syntax_errors or total_errors:
        click.echo(
            f"WARN: {total_errors} workflow error(s), {total_syntax_errors} notebook(s) with syntax errors. "
            "Review the WARN lines above before running the generated notebooks.",
            err=True,
        )
        ctx = click.get_current_context()
        ctx.exit(1)


@main.command()
@click.argument("manifest", type=click.Path(exists=True))
@click.option("-o", "--output", default="./output", help="Output directory")
@click.option(
    "--report",
    is_flag=True,
    default=False,
    help="Generate aggregate batch_report.md",
)
def generate(manifest, output, report):
    """Generate production notebooks from manifest.json."""
    _load_plugins()
    manifest_path = Path(manifest)
    output_path = Path(output)

    if manifest_path.is_file():
        manifests = [manifest_path]
    else:
        manifests = list(manifest_path.glob("**/*.json"))

    if not manifests:
        click.echo("No manifest files found.")
        return

    results = []
    for m in manifests:
        click.echo(f"Generating: {m.name}")
        try:
            wf = load_manifest(m)
            stats = generate_notebooks_v2(wf, output_path)
            results.append(stats)
            click.echo(f"  Done: {output_path / wf.name}/")
            for bad in stats.get("syntax_errors", []):
                click.echo(
                    f"  WARN: generated file has syntax error — {bad}", err=True
                )
        except Exception as e:
            click.echo(f"  Error: {e}", err=True)
            results.append(
                {
                    "name": m.stem,
                    "tools_total": 0,
                    "tools_converted": 0,
                    "avg_confidence": 0,
                    "unsupported_tools": [],
                    "errors": [str(e)],
                    "syntax_errors": [],
                }
            )

    if report:
        output_path.mkdir(parents=True, exist_ok=True)
        generate_batch_report(output_path, results)
        click.echo(f"Report: {output_path / 'batch_report.md'}")

    total_syntax_errors = sum(len(r.get("syntax_errors", [])) for r in results)
    total_errors = sum(len(r.get("errors", [])) for r in results)
    click.echo(f"\nDone. Generated {len(manifests)} workflow(s).")
    if total_syntax_errors or total_errors:
        click.echo(
            f"WARN: {total_errors} workflow error(s), {total_syntax_errors} notebook(s) with syntax errors. "
            "Review the WARN lines above before running the generated notebooks.",
            err=True,
        )
        ctx = click.get_current_context()
        ctx.exit(1)


@main.command()
@click.argument("source", type=click.Path(exists=True))
def analyze(source):
    """Analyze workflow without generating code."""
    source_path = Path(source)
    if source_path.is_file():
        files = [source_path]
    else:
        files = list(source_path.glob("**/*.yxmd")) + list(
            source_path.glob("**/*.yxzp")
        )
    for f in files:
        unpacked = unpack_source(f)
        try:
            wf = parse_yxmd(unpacked.workflow_path)
            order = resolve_dag(wf)
            click.echo(f"\nWorkflow: {wf.name}")
            click.echo(f"Tools: {len(wf.tools)}")
            supported = 0
            for tool_id in order:
                tool = wf.tools[tool_id]
                handler = get_handler(tool)
                is_supported = type(handler).__name__ != "UnsupportedHandler"
                if is_supported:
                    supported += 1
                status = "OK" if is_supported else "UNSUPPORTED"
                click.echo(
                    f"  [{status}] [{tool_id}] {tool.tool_type}: {tool.annotation}"
                )
            pct = supported / len(wf.tools) * 100 if wf.tools else 0
            click.echo(f"Coverage: {supported}/{len(wf.tools)} ({pct:.0f}%)")
        finally:
            unpacked.cleanup()


@main.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("-o", "--output", default="./output", help="Output directory")
@click.option(
    "--config",
    "config_path",
    default=None,
    type=click.Path(),
    help="Path to .alteryx2dbx.yml",
)
def document(source, output, config_path):
    """Generate migration documentation for workflow(s)."""
    source_path = Path(source)
    output_path = Path(output)

    if source_path.is_file():
        files = [source_path]
    else:
        files = list(source_path.glob("**/*.yxmd")) + list(
            source_path.glob("**/*.yxzp")
        )

    if not files:
        click.echo("No .yxmd or .yxzp files found.")
        return

    config_p = Path(config_path) if config_path else None
    config = load_config(Path.cwd(), config_path=config_p)

    results = []
    for f in files:
        click.echo(f"Documenting: {f.name}")
        unpacked = unpack_source(f)
        try:
            wf = parse_yxmd(unpacked.workflow_path)
            wf_output = output_path / wf.name
            report_path = generate_migration_report(wf, wf_output)
            click.echo(f"  Report: {report_path}")

            # Collect stats for portfolio
            execution_order = resolve_dag(wf)
            confidences = []
            supported = 0
            for tid in execution_order:
                tool = wf.tools[tid]
                handler = get_handler(tool)
                is_supported = type(handler).__name__ != "UnsupportedHandler"
                if is_supported:
                    supported += 1
                step = handler.convert(tool)
                confidences.append(step.confidence)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            readiness = (
                "Ready"
                if avg_conf > 0.9
                else "Needs Review"
                if avg_conf > 0.7
                else "Significant Manual Work"
            )
            results.append(
                {
                    "name": wf.name,
                    "tools_total": len(execution_order),
                    "avg_confidence": avg_conf,
                    "supported": supported,
                    "unsupported": len(execution_order) - supported,
                    "readiness": readiness,
                }
            )

            # Confluence publishing
            if config and config.get("confluence", {}).get("pat"):
                if confluence_available():
                    markdown = report_path.read_text(encoding="utf-8")
                    try:
                        publish_draft(config, wf.name, markdown)
                        click.echo("  Confluence draft created/updated")
                    except Exception as e:
                        click.echo(f"  Confluence error: {e}", err=True)
                else:
                    click.echo(
                        "  Install confluence support: pip install alteryx2dbx[confluence]"
                    )
        except Exception as e:
            click.echo(f"  Error: {e}", err=True)
        finally:
            unpacked.cleanup()

    if len(files) > 1:
        generate_portfolio_report(output_path, results)
        click.echo(f"Portfolio: {output_path / 'portfolio_report.md'}")

    if not config:
        click.echo(
            "\nTip: Create .alteryx2dbx.yml to enable Confluence publishing. See README."
        )
    elif not config.get("confluence", {}).get("pat"):
        click.echo(f"\n{pat_setup_guide()}")

    click.echo(f"\nDone. Documented {len(files)} workflow(s).")


@main.command()
def tools():
    """List supported Alteryx tools."""
    click.echo("Supported tool types:")
    for tool_type in sorted(_registry._type_handlers.keys()):
        handler = _registry._type_handlers[tool_type]
        click.echo(f"  {tool_type} ({handler.__name__})")
    click.echo(f"\nTotal: {len(_registry._type_handlers)} tool types")


@main.group()
@click.option(
    "--lessons-file",
    default=None,
    type=click.Path(),
    help="Path to lessons.jsonl",
)
@click.pass_context
def lessons(ctx, lessons_file):
    """Manage migration lessons learned."""
    ctx.ensure_object(dict)
    ctx.obj["store"] = LessonStore(
        Path(lessons_file).parent if lessons_file else None
    )


@lessons.command("add")
@click.option("--workflow", required=True)
@click.option("--symptom", required=True)
@click.option("--root-cause", required=True)
@click.option("--fix", required=True)
@click.option("--category", required=True, type=click.Choice(CATEGORIES))
@click.pass_context
def lessons_add(ctx, workflow, symptom, root_cause, fix, category):
    """Add a lesson from a migration experience."""
    store = ctx.obj["store"]
    lesson = Lesson(
        id=Lesson.new_id(),
        date=date.today().isoformat(),
        workflow=workflow,
        symptom=symptom,
        root_cause=root_cause,
        fix=fix,
        category=category,
    )
    store.add(lesson)
    click.echo(f"Lesson {lesson.id} added.")


@lessons.command("list")
@click.option("--category", default=None)
@click.option("--unpromoted", is_flag=True)
@click.pass_context
def lessons_list(ctx, category, unpromoted):
    """List recorded lessons."""
    store = ctx.obj["store"]
    items = store.list_all(category=category, unpromoted_only=unpromoted)
    if not items:
        click.echo("No lessons found.")
        return
    for lesson in items:
        status = "[promoted]" if lesson.promoted else "[active]"
        auto = " (auto)" if lesson.auto_captured else ""
        click.echo(
            f"  {lesson.id} {status}{auto} [{lesson.category}] {lesson.symptom}"
        )


@lessons.command("promote")
@click.argument("lesson_id")
@click.pass_context
def lessons_promote(ctx, lesson_id):
    """Mark a lesson as promoted (encoded into tool rules)."""
    store = ctx.obj["store"]
    if store.promote(lesson_id):
        click.echo(f"Lesson {lesson_id} promoted.")
    else:
        click.echo(f"Lesson {lesson_id} not found.")
