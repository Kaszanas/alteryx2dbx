"""Publish migration reports as Confluence draft pages."""
from __future__ import annotations

import re

try:
    from atlassian import Confluence

    _ATLASSIAN_AVAILABLE = True
except ImportError:
    Confluence = None
    _ATLASSIAN_AVAILABLE = False


def confluence_available() -> bool:
    return _ATLASSIAN_AVAILABLE


def _get_confluence_client(config: dict):
    conf = config["confluence"]
    return Confluence(url=conf["url"], token=conf["pat"])


def _markdown_to_storage(markdown: str) -> str:
    lines = markdown.split("\n")
    result = []
    in_code_block = False
    code_lang = ""
    code_lines = []

    for line in lines:
        if line.startswith("```") and not in_code_block:
            in_code_block = True
            code_lang = line[3:].strip()
            code_lines = []
            continue
        elif line.startswith("```") and in_code_block:
            in_code_block = False
            code_content = "\n".join(code_lines)
            result.append(
                f'<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">{code_lang or "text"}</ac:parameter>'
                f"<ac:plain-text-body><![CDATA[{code_content}]]></ac:plain-text-body></ac:structured-macro>"
            )
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if line.startswith("# "):
            result.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            result.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            result.append(f"<h3>{line[4:]}</h3>")
        elif line.strip().startswith("- [ ]"):
            content = _inline_formatting(line.strip()[5:].strip())
            result.append(f"<ac:task><ac:task-body>{content}</ac:task-body></ac:task>")
        elif line.strip().startswith("- "):
            content = _inline_formatting(line.strip()[2:])
            result.append(f"<li>{content}</li>")
        elif "|" in line and not line.strip().startswith("|--"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            row = "".join(f"<td>{_inline_formatting(c)}</td>" for c in cells)
            result.append(f"<tr>{row}</tr>")
        elif line.strip().startswith("|--"):
            continue
        elif not line.strip():
            result.append("<br/>")
        else:
            result.append(f"<p>{_inline_formatting(line)}</p>")

    return "\n".join(result)


def _inline_formatting(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def publish_draft(config: dict, workflow_name: str, markdown: str) -> dict | None:
    confluence = _get_confluence_client(config)
    conf = config["confluence"]
    space = conf["space"]
    parent_page_title = conf.get("parent_page", "")

    parent_id = None
    if parent_page_title:
        parent = confluence.get_page_by_title(space, parent_page_title)
        if parent:
            parent_id = parent["id"]

    title = f"Migration Report: {workflow_name}"
    existing = confluence.get_page_by_title(space, title)
    storage_body = _markdown_to_storage(markdown)

    if existing:
        return confluence.update_page(
            page_id=existing["id"],
            title=title,
            body=storage_body,
            type="page",
            status="draft",
        )
    else:
        return confluence.create_page(
            space=space,
            title=title,
            body=storage_body,
            parent_id=parent_id,
            type="page",
            status="draft",
        )


def pat_setup_guide() -> str:
    return (
        "To publish to Confluence, you need a Personal Access Token (PAT):\n"
        "\n"
        "1. Go to your Confluence instance > Profile > Personal Access Tokens\n"
        "2. Click 'Create token'\n"
        "3. Give it a name like 'alteryx2dbx'\n"
        "4. Copy the token\n"
        "5. Add it to your .alteryx2dbx.yml:\n"
        "   confluence:\n"
        "     pat: your-token-here\n"
        "\n"
        "   Or set the CONFLUENCE_PAT environment variable.\n"
        "   On Databricks, use: dbutils.secrets.get('confluence', 'pat')\n"
    )
