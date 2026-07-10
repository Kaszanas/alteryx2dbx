# Security Audit: Data Handling & Egress

Scope: does converting a `.yxmd`/`.yxzp` workflow with `alteryx2dbx` leak the
source file or the data/business logic it describes — over the network, into
shared/multi-tenant locations, or into artifacts a user might not expect to
carry sensitive content? Every module under `src/alteryx2dbx/` was audited for
network calls, subprocess/`eval`/`exec` usage, file writes outside the CLI's
`-o` output directory, log/console output, and exactly which fields survive
from the parsed XML into each generated artifact. This document records
findings and severities only — no remediation was made as part of this pass.

## Executive summary

`alteryx2dbx` makes **no outbound network calls, has no telemetry, and does
not fetch or execute remote code** in its default configuration. The two real
egress paths that exist — Confluence publishing and Box SDK calls — are both
opt-in and only ever talk to a destination the user has explicitly configured
(their own Confluence space, or the Box file/folder IDs already present in
the source Alteryx workflow). The real risk this audit surfaces is **not**
"data leaving to a third party" — it's that the tool captures the *complete*
raw Alteryx XML (formulas, DB connection strings, file paths) into
`manifest.json` and, for unsupported tools, into the generated notebook
comments — meaning raw workflow content propagates further into artifacts
the user generates and may share (e.g. checking `manifest.json` into a repo,
emailing a `conversion_report.md`) than they might assume from a quick skim.

## Methodology

Two independent passes covered every file under `src/alteryx2dbx/`:

1. **Network/external-service pass** — grepped for HTTP client libraries,
   `boxsdk`/`atlassian-python-api` usage, telemetry/analytics SDKs, hardcoded
   external hostnames, `subprocess`/`os.system`/`eval`/`exec`, and how
   credentials (Confluence PAT, Box JWT) are read and whether they're ever
   logged or written to disk.
2. **Filesystem/logging pass** — traced `.yxzp` temp-extraction and cleanup,
   the `lessons.jsonl` learning-loop storage, every `print`/`click.echo`/
   `logging` call site, and exactly which fields from the parsed workflow
   end up in `manifest.json`, the generated `.py` notebooks, and the
   `*_report.md` files.

Findings below were then individually re-verified by reading the cited
source directly (not just trusting the initial pass) before being written up.

## Findings

### [Medium] Raw Alteryx XML embedded unredacted in `manifest.json`
`src/alteryx2dbx/parser/xml_parser.py:160`:
```python
config["_raw_xml"] = ET.tostring(config_el, encoding="unicode")
```
Every tool's full `<Configuration>` XML block — formulas, join keys, DB
connection strings, file paths — is stored verbatim in `config["_raw_xml"]`,
in addition to the tool-specific fields already extracted. This flows through
`AlteryxTool.to_dict()` (`parser/models.py:62-70`) into `manifest.json` via
`manifest.py`'s `serialize_manifest()`. `manifest.json` is therefore a
lossless dump of the original workflow's business logic — this is the root
data source for every other finding below. This is by design (the README
describes the manifest as "an inspectable, editable intermediate
representation"), but it means anyone who receives `manifest.json` receives
the complete original workflow content, not a redacted summary.

### [Medium] That raw XML is written verbatim into generated notebooks for unsupported tools
`src/alteryx2dbx/handlers/base.py` (`UnsupportedHandler.convert`):
```python
raw_xml = tool.config.get("_raw_xml", "<!-- no config -->")
code = (
    f"# ⚠️ UNSUPPORTED TOOL: {tool.tool_type} (Tool ID: {tool.tool_id})\n"
    ...
    + "\n".join(f"# {line}" for line in raw_xml.split("\n"))
    ...
)
```
For any tool type without a dedicated handler, the full raw XML is embedded
as `#`-prefixed comments directly in the output `.py` notebook, written to
the user's `-o` directory. The project's own "Limitations" list (README)
names in-database connectors (In-DB Connect, In-DB Filter) as unsupported —
these are exactly the tool types most likely to carry ODBC/OLEDB connection
strings and internal server names in their raw config.

### [Low-Medium] Full expressions and paths embedded in `migration_report.md`
`src/alteryx2dbx/document/report.py`:
- `_data_source_inventory` / `_output_inventory` (lines 128, 150): source
  and destination `file_path`/`File` values, verbatim, including UNC paths.
- `_business_logic_summary` (lines 172, 176-182, 189-191): Filter
  expressions, Join field mappings, and Formula field/expression pairs,
  verbatim.

This is the intended purpose of a migration report, not a bug — but it's
worth naming explicitly because it's the payload that reaches Confluence if
that integration is enabled (see next finding), and because `document`
output is more likely to be shared with non-engineering stakeholders than
`manifest.json` or generated code.

### [Low, opt-in only] Confluence publish sends that report externally
`src/alteryx2dbx/document/confluence.py:publish_draft()`, invoked from
`cli.py`'s `document` command only when the user has set `confluence.pat` in
`.alteryx2dbx.yml` or `CONFLUENCE_PAT`. Verified: the payload sent to
Confluence is only the `migration_report.md` markdown content (converted to
Confluence storage format) plus the workflow name used for the page title —
no credentials, no `manifest.json`, no raw `_raw_xml`. The PAT is used
solely to construct the `Confluence(url=..., token=...)` client
(`confluence.py:22`) and is never echoed, logged, or written to any output
file (confirmed via grep across `manifest.py` and `document/report.py`).
Rated Low, not a defect, because it only activates when the user explicitly
opts in and only sends to a destination they configured themselves.

### [Low] Hardcoded shared Databricks path for `lessons.jsonl`
`src/alteryx2dbx/lessons/store.py:8-14`:
```python
if os.environ.get("DATABRICKS_RUNTIME_VERSION") or os.environ.get("IS_SERVERLESS"):
    self.path = Path("/Workspace/Shared/alteryx2dbx/lessons.jsonl")
```
Whenever the tool detects it's running on Databricks, lessons are written to
a fixed **Shared** workspace path, visible to every user with access to that
workspace's Shared folder — not scoped per-user, with no opt-out. Most
auto-captured content is abstract (tool names, confidence scores, generic
`AMBIGUOUS` categories), but `auto_capture()` (`lessons/capture.py:15-42`)
does copy step notes verbatim when they contain `"AMBIGUOUS"`, and several
handlers embed real field/column names into those notes (e.g.
`summarize.py`'s ambiguous-aggregation note includes the actual field name).
Manual `alteryx2dbx lessons add` entries can also contain arbitrary free
text a user types, with no warning that the destination is workspace-shared.

### [Info] Console/log output can echo full local paths and raw exception text
`cli.py`'s error-passthrough sites (`click.echo(f"  Error: {e}", err=True)`,
present in `parse`, `convert`, `generate`, `document`) surface raw exception
messages on failure. Since `unpack_source()` raises
`FileNotFoundError(f"Source file not found: {source}")` with the full path
embedded, and XML parse errors can include fragments of the offending
markup, a failed run can print a full local file path or an XML snippet to
the terminal/CI log. This is local-console exposure only (stdout/stderr on
the machine running the CLI), not a network leak — flagged for completeness
since CI logs are sometimes retained/shared beyond the original operator.

### [Info] `.yxzp` temp-extraction cleanup relies on `finally`, not crash-resistant
`src/alteryx2dbx/parser/unpacker.py:_unpack_yxzp()` extracts to
`tempfile.mkdtemp(prefix="alteryx2dbx_")` and `UnpackResult.cleanup()` does
`shutil.rmtree(self._temp_dir)`. Verified all 5 call sites in `cli.py`
(`parse`, `convert`, `analyze`, `document`, batch `parse`) wrap the unpack
in `try/finally: unpacked.cleanup()` — cleanup is correctly guaranteed for
every normal exception path. It is **not** guaranteed on a hard crash
(SIGKILL, OOM, power loss), since `finally` only runs during ordinary Python
stack unwinding — there's no `atexit`/signal-handler fallback. Extracted
`.yxzp` contents (workflow XML, macros, assets) could linger in the OS temp
dir with a predictable `alteryx2dbx_*` prefix after such a crash.

### [Info, confirmed clean] Box SDK code is generated text, never executed locally
`generator/utils_notebook.py`, `handlers/box_input.py`, `handlers/box_output.py`
only emit **string templates** containing `from boxsdk import ...` and
`box_client.file(...).content()`/`upload_stream(...)` calls, written into the
*generated* `_utils.py`/notebook output. `alteryx2dbx`'s own process never
imports `boxsdk` — confirmed via grep (no `import boxsdk` outside the
template string). That generated code only runs later, inside the user's own
Databricks workspace, authenticated via a Databricks Secret scope the user
configures there, and uploads/downloads only to the Box file/folder IDs
already present in the original Alteryx workflow. Called out explicitly
because at a glance this looks like a live egress path and it is not.

### [Info, confirmed clean] No telemetry, no hidden network calls, no remote plugin fetching
Verified via full-repo grep: zero matches for `requests`/`httpx`/`urllib`/
`socket` imports, and zero matches for telemetry/analytics SDK names
(`sentry`, `posthog`, `segment`, `mixpanel`) anywhere in `src/`. The only
literal `https://` URL in the source tree is inert text inside a generated
Databricks starter notebook (`starter.py`, a `%pip install git+https://
github.com/...` comment) — it is never executed by the CLI itself, only by
the user, later, if they run that notebook cell. The plugin system
(`plugins/loader.py`) loads only local Python files: entry points already
`pip install`ed on the user's machine, paths listed in the user's own
`.alteryx2dbx.yml`, or files in a local `./plugins/` directory — there is no
URL-based plugin index or download-and-execute mechanism.

## Function-level coverage

| Module | Verdict |
|---|---|
| `cli.py` | Orchestrates all I/O; every write goes through `-o`/`--output` args or `lessons.jsonl`; no network calls except delegating to `document/confluence.py` when opted in. |
| `parser/xml_parser.py`, `parser/models.py` | Pure parsing, no I/O beyond reading the source file; captures raw XML into `_raw_xml` (see findings). |
| `parser/unpacker.py` | Local temp-dir extraction only; no network. |
| `parser/schema_drift.py`, `parser/column_tracker.py` | Pure in-memory comparison logic, no I/O. |
| `dag/resolver.py` | Pure graph computation (NetworkX), no I/O. |
| `handlers/*.py` (all 32) | Pure string/code generation from parsed tool config; no I/O, no network. `base.py`'s `UnsupportedHandler` is the one place raw XML reaches generated output (see findings). `box_input.py`/`box_output.py` emit `boxsdk` template text only. |
| `transpiler/expression_parser.py`, `transpiler/expression_emitter.py` | Pure Lark-grammar parsing/string emission, no I/O. |
| `generator/notebook.py`, `notebook_v2.py`, `config.py`, `config_notebook.py`, `utils_notebook.py`, `validator.py`, `validator_v2.py`, `report.py`, `batch_report.py` | All writes strictly under the caller-supplied output directory; no network. |
| `manifest.py` | Serializes/deserializes the parsed IR to/from JSON at a caller-supplied path; carries `_raw_xml` through losslessly (see findings). |
| `document/report.py`, `document/mermaid.py`, `document/portfolio.py` | Writes `migration_report.md`/`portfolio_report.md` under the caller-supplied output dir; embeds expressions/paths (see findings). |
| `document/config.py` | Reads `.alteryx2dbx.yml` and `CONFLUENCE_PAT` env var; no writes, no network. |
| `document/confluence.py` | The one opt-in network call in the codebase (see findings); optional dependency, guarded by `try/except ImportError`. |
| `lessons/models.py` | Pure dataclass, no I/O. |
| `lessons/capture.py` | Pure in-memory analysis of conversion results into `Lesson` objects, no I/O. |
| `lessons/store.py` | Local/append-only JSONL storage; one hardcoded shared-path case on Databricks (see findings). |
| `plugins/loader.py`, `plugins/types.py` | Loads local Python only — entry points, config-listed paths, or `./plugins/` dir; no remote fetch. |
| `fixes.py` | Pure string-transform passes over generated code, no I/O. |
| `starter.py` | Writes a static starter-notebook template to a caller-supplied path; the notebook's *contents* (not executed here) reference `%pip install` from GitHub and shell out to the CLI when the user runs it later in Databricks. |

## Answer to the core question

By default — no `.alteryx2dbx.yml` Confluence configuration — running
`alteryx2dbx convert`/`parse`/`generate`/`analyze`/`document` sends **nothing
over the network** and writes only to the user-specified `-o` directory plus
the OS temp directory (cleaned up on normal exit; see the crash-resilience
note above for the one edge case). The Alteryx file's full content, including
raw XML with formulas and connection details, **does** end up unredacted in
`manifest.json` and, for unsupported tools, as comments in the generated
notebooks — this is a "leak" only in the sense that it propagates further
within artifacts the user already controls and intentionally generates; it
does not leave the local machine unless the user separately opts into
Confluence publishing, in which case only the `migration_report.md` content
(not the raw manifest) is sent, and only to the Confluence instance the user
configured.
