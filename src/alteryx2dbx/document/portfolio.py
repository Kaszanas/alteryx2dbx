"""Generate portfolio_report.md for batch documentation runs."""

from __future__ import annotations

from pathlib import Path
from datetime import date


def generate_portfolio_report(output_dir: Path, results: list[dict]) -> Path:
    total_workflows = len(results)
    avg_confidence = (
        sum(r["avg_confidence"] for r in results) / total_workflows
        if results
        else 0
    )
    total_tools = sum(r["tools_total"] for r in results)

    readiness_counts = {}
    for r in results:
        readiness = r.get("readiness", "Unknown")
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1

    lines = [
        "# Portfolio Assessment",
        "",
        "## Summary",
        "",
        f"- **Total workflows**: {total_workflows}",
        f"- **Total tools**: {total_tools}",
        f"- **Average confidence**: {avg_confidence:.0%}",
    ]
    for readiness, count in sorted(readiness_counts.items()):
        lines.append(f"- **{readiness}**: {count} workflow(s)")
    lines.append(f"- **Generated**: {date.today().isoformat()}")
    lines.append("")

    lines.append("## Workflows")
    lines.append("")
    lines.append("| Workflow | Tools | Confidence | Readiness | Unsupported |")
    lines.append("|----------|-------|------------|-----------|-------------|")
    for r in sorted(results, key=lambda x: x["avg_confidence"]):
        lines.append(
            f"| [{r['name']}]({r['name']}/migration_report.md) "
            f"| {r['tools_total']} "
            f"| {r['avg_confidence']:.0%} "
            f"| {r.get('readiness', '?')} "
            f"| {r.get('unsupported', 0)} |"
        )
    lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "portfolio_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
