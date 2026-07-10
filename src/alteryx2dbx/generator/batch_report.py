"""Generate aggregate batch_report.md from conversion results."""

from __future__ import annotations

from pathlib import Path


def generate_batch_report(output_dir: Path, results: list[dict]) -> None:
    """Generate aggregate batch_report.md from conversion results.

    results: list of dicts with keys: name, tools_total, tools_converted,
             avg_confidence, unsupported_tools (list of str), errors (list of str)
    """
    total_workflows = len(results)
    total_tools = sum(r["tools_total"] for r in results)
    total_converted = sum(r["tools_converted"] for r in results)
    overall_coverage = (
        (total_converted / total_tools * 100) if total_tools else 0
    )
    avg_confidence = (
        sum(r["avg_confidence"] for r in results) / len(results)
        if results
        else 0
    )

    lines = [
        "# Batch Conversion Report\n",
        "## Summary\n",
        f"- **Workflows converted**: {total_workflows}",
        f"- **Total tools**: {total_tools}",
        f"- **Tools converted**: {total_converted} ({overall_coverage:.0f}%)",
        f"- **Average confidence**: {avg_confidence:.0%}",
        "",
        "## Per-Workflow Details\n",
        "| Workflow | Tools | Coverage | Confidence | Unsupported |",
        "|----------|-------|----------|------------|-------------|",
    ]

    for r in sorted(results, key=lambda x: x["avg_confidence"]):
        coverage = (
            r["tools_converted"] / r["tools_total"] * 100
            if r["tools_total"]
            else 0
        )
        unsupported = ", ".join(r.get("unsupported_tools", [])[:3])
        if len(r.get("unsupported_tools", [])) > 3:
            unsupported += f" +{len(r['unsupported_tools']) - 3} more"
        lines.append(
            f"| {r['name']} | {r['tools_total']} | {coverage:.0f}% | {r['avg_confidence']:.0%} | {unsupported} |"
        )

    if any(r.get("errors") for r in results):
        lines.extend(["", "## Errors\n"])
        for r in results:
            for err in r.get("errors", []):
                lines.append(f"- **{r['name']}**: {err}")

    (output_dir / "batch_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
