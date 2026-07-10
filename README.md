# alteryx2dbx

Convert Alteryx `.yxmd` and `.yxzp` workflows to PySpark Databricks notebooks. Deterministic, rule-based, no LLMs.

## Why This Exists

Migrating Alteryx workflows to Databricks is tedious. Teams walk through each workflow, read the XML, and rewrite the logic in PySpark by hand. Some try LLMs, but they hallucinate PySpark APIs, invent functions that don't exist, and silently change semantics around null handling, case sensitivity, and string indexing.

`alteryx2dbx` takes a different approach. It parses the Alteryx XML directly, resolves the DAG, and emits PySpark through a rule-based transpiler. Every expression mapping is explicit and auditable. When something can't be converted, it's marked as unsupported with the original XML preserved in comments. Nothing is silently dropped.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

**From source (recommended while pre-PyPI)**

```bash
git clone https://github.com/aggarwalkartik/alteryx2dbx.git
cd alteryx2dbx
uv sync
uv run alteryx2dbx --help    # verify
```

From here, prefix every CLI example below with `uv run` — e.g. `uv run alteryx2dbx convert ...`.

**As a global CLI** (once published to PyPI)

```bash
uv tool install alteryx2dbx
alteryx2dbx --help
```

**On Databricks**

Install directly from GitHub (works today, no PyPI needed):

```python
# Cell 1
%pip install --no-cache-dir --force-reinstall git+https://github.com/aggarwalkartik/alteryx2dbx.git

# Cell 2
%restart_python

# Cell 3
import alteryx2dbx
print(alteryx2dbx.__version__)          # verify
```

Then generate a starter notebook with widgets for the paths so you don't retype them:

```python
# Cell 4
!alteryx2dbx init -o /Workspace/Users/<you@company.com>/alteryx2dbx_starter.py
```

Open `alteryx2dbx_starter.py` in the Databricks UI — it's a real notebook with three widgets (`workflow_path`, `output_dir`, `mode`) and an execute cell. Fill in the widgets, run.

Once published to PyPI, replace Cell 1 with `%pip install alteryx2dbx`. Everything else is the same. The older `dbutils.library.restartPython()` is equivalent to `%restart_python` if you prefer.

**Path conventions on Databricks**

- **Inputs** (`.yxmd` files): put them in a Unity Catalog Volume — `/Volumes/<catalog>/<schema>/alteryx/`. Volumes are the designed-for-data path and avoid the "spaces in Workspace paths break shell commands" problem.
- **Outputs** (generated notebooks): write to a Workspace folder — `/Workspace/Users/<you@company.com>/…` — so you can open them in the Databricks UI.

## First run

A sample workflow ships with the repo under `examples/`. Convert it end-to-end:

```bash
uv run alteryx2dbx convert examples/simple_filter.yxmd -o ./output --full
ls ./output/simple_filter/
# _config.py  _utils.py  01_load_sources.py  02_transformations.py
# 03_write_outputs.py  04_validate.py  05_orchestrate.py
# manifest.json  conversion_report.md
```

Open `conversion_report.md` for per-tool confidence scores and any semantic fixes that were applied automatically.

## Usage

### Parse a workflow to manifest

```bash
alteryx2dbx parse workflow.yxmd -o manifest.json        # single file
alteryx2dbx parse workflow.yxzp -o manifest.json        # .yxzp package
alteryx2dbx parse ./workflows/ -o ./manifests/           # batch (mixed .yxmd/.yxzp)
```

Parses the workflow XML into a JSON manifest. This is an inspectable, editable intermediate representation. Parse once, generate many times.

### Generate production notebooks from manifest

```bash
alteryx2dbx generate manifest.json -o ./output
alteryx2dbx generate ./manifests/ -o ./output --report   # batch + aggregate report
```

Emits serverless-safe Databricks notebooks with `_config.py` (parameterized with widgets), `_utils.py` (standard helpers), transformation notebooks, validation, and orchestration.

### Convert a single workflow (quick mode)

```bash
alteryx2dbx convert workflow.yxmd -o ./output            # v1 output
alteryx2dbx convert workflow.yxzp -o ./output --full     # v2 serverless-safe output
```

### Convert a directory of workflows (batch)

```bash
alteryx2dbx convert ./workflows/ -o ./output
alteryx2dbx convert ./workflows/ -o ./output --full      # v2 output
```

This recursively finds all `.yxmd` and `.yxzp` files and converts each one into its own output folder. Use `--full` for the v2 generator (serverless-safe, production notebooks).

### Batch mode with summary report

```bash
alteryx2dbx convert ./workflows/ -o ./output --report
```

When `--report` is passed, an aggregate `batch_report.md` is generated in the output directory with:
- Total workflow count, tool count, and overall coverage
- Per-workflow table sorted by confidence (lowest first)
- Unsupported tool list per workflow
- Error summary for any workflows that failed to convert

### Document a workflow (migration report)

```bash
alteryx2dbx document workflow.yxmd -o ./output
alteryx2dbx document ./workflows/ -o ./output          # batch + portfolio report
```

Generates a comprehensive `migration_report.md` with executive summary, data flow diagram (Mermaid), source/output inventory, business logic summary, and manual review checklist.

**On Databricks:**

```python
%pip install --no-cache-dir --force-reinstall git+https://github.com/aggarwalkartik/alteryx2dbx.git
%restart_python

# Upload your .yxmd files to a Volume, then:
!alteryx2dbx document /Volumes/catalog/schema/workflows/ -o /Volumes/catalog/schema/output/
```

**Confluence integration (optional):**

Create `.alteryx2dbx.yml` in the repo root:

```yaml
confluence:
  url: https://company.atlassian.net
  space: DATA-MIGRATION
  parent_page: "Alteryx Migration Reports"
```

Set your PAT via environment variable or Databricks secret:

```python
import os
os.environ["CONFLUENCE_PAT"] = dbutils.secrets.get("confluence", "pat")
```

When configured, `document` automatically creates Confluence **draft** pages (never publishes directly).

### Analyze a workflow (dry run)

```bash
alteryx2dbx analyze workflow.yxmd
alteryx2dbx analyze workflow.yxzp
```

Prints every tool in execution order with its support status and coverage percentage. No files are written.

```
Workflow: simple_filter
Tools: 3
  [OK] [1] DbFileInput: Input Customers
  [OK] [2] Filter: Filter Active High Rev
  [OK] [3] DbFileOutput: Output Active Customers
Coverage: 3/3 (100%)
```

### List supported tools

```bash
alteryx2dbx tools
```

### Generate a Databricks starter notebook

```bash
alteryx2dbx init                                           # writes ./alteryx2dbx_starter.py
alteryx2dbx init -o /Workspace/Users/you@company.com/starter.py
```

Writes a Databricks notebook (widgets + install + run). Open the file in the Databricks UI, fill in `workflow_path`, `output_dir`, and `mode`, and run. See the **On Databricks** block in the Install section for the full flow.

## Output Structure

### v2 output (`generate` or `convert --full`)

```
output/<workflow_name>/
    _config.py                # Databricks notebook: catalog/schema/env via widgets, source/output paths
    _utils.py                 # Databricks notebook: log_step, null_safe_join, check_row_count, safe_cast
    01_load_sources.py        # Databricks notebook: reads source data
    02_transformations.py     # Databricks notebook: business logic in DAG order
    03_write_outputs.py       # Databricks notebook: writes results to targets
    04_validate.py            # Databricks notebook: 8-check validation with 3-tier verdict
    05_orchestrate.py         # Databricks notebook: %run chain (config -> utils -> load -> transform -> write)
    manifest.json             # Parsed workflow IR (for audit trail / re-generation)
    conversion_report.md      # Per-tool confidence, applied semantic fixes, review notes
```

The v2 output is serverless-safe (no `.cache()`, no RDDs, no global temp views) and uses `%run` chains for notebook orchestration.

### v1 output (`convert` without `--full`)

```
output/<workflow_name>/
    01_load_sources.py        # Databricks notebook: reads source data
    02_transformations.py     # Databricks notebook: filters, joins, formulas, etc.
    03_orchestrate.py         # Databricks notebook: runs 01 + 02, writes outputs
    04_validate.py            # Databricks notebook: DataComPy comparison boilerplate
    config.yml                # Workflow metadata, source/output paths
    conversion_report.md      # Per-tool confidence scores and review notes
```

## Box.com Connector Support

Workflows that use Box Input/Output tools (marketplace add-ons) are fully supported. The generated notebooks automatically:

- Download files from Box via the Box Python SDK (`boxsdk`)
- Upload results back to Box
- Authenticate using JWT credentials stored in Databricks Secrets

When Box tools are detected, `_config.py` adds a `BOX_SECRET_SCOPE` widget and `_utils.py` includes a `get_box_client()` helper. No manual wiring needed.

**Setup on Databricks:**

1. Create a Box JWT application and download the JSON config
2. Store it as a Databricks secret: `dbutils.secrets.put("box", "jwt_config", "<json>")`
3. Run the converted notebooks. They'll authenticate automatically.

Box support is format-aware: CSV, Excel, and JSON files are handled. Avro is flagged for manual implementation.

## Supported Tools (34 tool types)

| Alteryx Tool | PySpark Equivalent | Handler |
|--------------|--------------------|---------|
| InputData / DbFileInput | `spark.read.format(...)` (CSV, Excel, Parquet) | `InputDataHandler` |
| TextInput | `spark.createDataFrame(...)` from inline data | `TextInputHandler` |
| DynamicInput | `spark.read` with TODO for dynamic path resolution | `DynamicInputHandler` |
| OutputData / DbFileOutput | `df.write.format(...)` | `OutputDataHandler` |
| Box Input | `boxsdk` download → `pd.read_csv/excel/json` → `spark.createDataFrame()` | `BoxInputHandler` |
| Box Output | `df.toPandas()` → `boxsdk` upload | `BoxOutputHandler` |
| Browse / BrowseV2 | `display(df)` / `df.show()` | `BrowseHandler` |
| Filter | `df.filter(expr)` with True/False branch outputs | `FilterHandler` |
| Formula | `df.withColumn(name, expr)` per formula field | `FormulaHandler` |
| MultiFieldFormula | `df.withColumn()` applied across matching columns | `MultiFieldFormulaHandler` |
| MultiRowFormula | `F.lag()` / `F.lead()` window functions | `MultiRowFormulaHandler` |
| Select / AlteryxSelect | `df.select(...)`, `df.drop(...)`, `df.withColumnRenamed(...)` | `SelectHandler` |
| Join | `df.join(other, cond, type)` with joined/left-only/right-only outputs | `JoinHandler` |
| Union | `df.unionByName(other, allowMissingColumns=True)` | `UnionHandler` |
| AppendFields | `df.crossJoin(other)` | `AppendFieldsHandler` |
| FindReplace | `F.regexp_replace()` / `F.when().otherwise()` | `FindReplaceHandler` |
| Sort | `df.orderBy(...)` | `SortHandler` |
| Sample | `df.limit(n)` / `df.sample(fraction)` | `SampleHandler` |
| Unique | `df.dropDuplicates()` with unique/duplicate branch outputs | `UniqueHandler` |
| Summarize | `df.groupBy(...).agg(...)` (Sum, Count, Avg, Min, Max, First, Last, CountDistinct, Concat) | `SummarizeHandler` |
| CrossTab | `df.groupBy().pivot().agg()` | `CrossTabHandler` |
| Transpose | `F.stack()` unpivot | `TransposeHandler` |
| DataCleansing | `F.trim()`, `F.lower()`, null removal per column | `DataCleansingHandler` |
| RegEx | `F.regexp_extract()` / `F.regexp_replace()` (match, parse, replace modes) | `RegExHandler` |
| TextToColumns | `F.split()` with column expansion | `TextToColumnsHandler` |
| DateTime | `F.to_timestamp()` / `F.date_format()` with format conversion | `DateTimeHandler` |
| RecordID | `F.monotonically_increasing_id()` | `RecordIDHandler` |
| AutoField | Pass-through (Spark infers types) | `AutoFieldHandler` |
| CountRecords | `df.count()` into single-row DataFrame | `CountRecordsHandler` |
| RunningTotal | `F.sum().over(Window)` | `RunningTotalHandler` |
| GenerateRows | `spark.range()` with expression-based row generation | `GenerateRowsHandler` |
| Tile | `F.ntile()` / `F.percent_rank()` window functions | `TileHandler` |

Unsupported tools are passed through with a `TODO` comment and the original XML config preserved for manual conversion.

## Expression Transpiler (80+ functions)

Alteryx formula expressions are parsed with a Lark grammar and transpiled to PySpark column expressions. The transpiler handles:

- **Arithmetic**: `+`, `-`, `*`, `/`, `%`
- **Comparisons**: `=`, `!=`, `>`, `>=`, `<`, `<=`
- **Logical operators**: `AND`, `OR`, `NOT`
- **Conditionals**: `IF/ELSEIF/ELSE/ENDIF` and `IIF()`
- **IN expressions**: `[Field] IN (1, 2, 3)` to `F.col("Field").isin(...)`
- **Switch**: `Switch([Field], default, val1, res1, ...)` to `F.when().when()...otherwise()`
- **Field references**: `[FieldName]` to `F.col("FieldName")`
- **Row references**: `[Row-1:Revenue]` to `F.lag(F.col("Revenue"), 1)`

### String functions
`Trim`, `TrimLeft`, `TrimRight`, `Length`, `Uppercase`, `Lowercase`, `TitleCase`, `ReverseString`, `Left`, `Right`, `Substring`, `Mid`, `Contains`, `StartsWith`, `EndsWith`, `FindString`, `GetWord`, `PadLeft`, `PadRight`, `Replace`, `ReplaceFirst`, `ReplaceChar`, `CountWords`

### Numeric functions
`Round`, `Ceil`, `Floor`, `Abs`, `Pow`, `Sqrt`, `Log`, `Log10`, `Log2`, `Exp`, `Min`, `Max`, `Sign`, `Rand`, `Sin`, `Cos`, `Tan`, `Asin`, `Acos`, `Atan`, `Atan2`

### Conversion functions
`ToString`, `ToNumber`, `ToInteger`, `ToDate`, `ToDateTime`

### Null handling
`IsNull`, `IsEmpty`, `Coalesce`, `IfNull`, `NullIf`

### Type testing
`IsNumber`, `IsInteger`

### RegEx functions
`RegEx_Match`, `RegEx_Replace`

### Date/Time functions
`DateTimeNow`, `DateTimeToday`, `DateTimeFormat`, `DateTimeParse`, `DateTimeAdd`, `DateTimeDiff`, `DateTimeYear`/`Year`, `DateTimeMonth`/`Month`, `DateTimeDay`/`Day`, `DateTimeHour`/`Hour`, `DateTimeMinutes`/`Minute`, `DateTimeSeconds`/`Second`, `DateTimeDayOfWeek`/`DayOfWeek`, `DateTimeFirstOfMonth`, `DateTimeTrim`

### Semantic corrections applied automatically

| Alteryx Behavior | PySpark Translation | Why |
|------------------|---------------------|-----|
| `=` is case-insensitive for strings | `F.lower(col) == F.lit("value".lower())` | Alteryx `=` ignores case; Spark `==` does not |
| `Substring(field, 0, 3)` is 0-based | `F.substring(col, 1, 3)` | Alteryx uses 0-based indexing; Spark uses 1-based |
| `FindString` returns 0-based position | `F.locate(...) - 1` | Preserves original index semantics |
| `=` with non-string values | `.eqNullSafe(...)` | Prevents silent null propagation |

## Features

- **.yxzp support**: Packaged Alteryx workflows (ZIP archives) are automatically extracted and parsed
- **Serverless-safe output** (v2): No `.cache()`, no RDDs, no global temp views. Works on both Databricks serverless and classic clusters.
- **Traceability**: Every generated code block is annotated with its source Alteryx tool ID, type, and annotation. When validation fails on a column, you can trace it straight back to the tool that produced it.
- **9 semantic auto-fixes**: Known Alteryx-to-PySpark pitfalls are automatically detected and fixed. Includes case-insensitive joins, null-safe equality, decimal casting, COALESCE typing, safe date parsing (`TRY_TO_DATE`), safe casting (`TRY_CAST`), float64 key detection, `withColumn` loop warnings, and date placeholder clamping.
- **8-check validation with 3-tier verdicts**: Row count, schema comparison, column order, column types, aggregates, null counts, DataComPy row-level matching, and auto-detected join keys. Results in one of three verdicts: Identical, Code Logic Verified, or Fail. Supports `VOLATILE_COLUMNS` and `KNOWN_DIFFERENCES` configs to handle expected timing differences.
- **Schema drift detection**: Compares ODBC metadata (RecordInfo) against Select tool configs to catch stale column references before code is generated. Warnings surface in both the generated notebooks and the conversion report.
- **Column mapping warnings**: Walks the DAG to detect `STALE_REF` fields that exist in Select configs but not in upstream tool outputs. Catches a whole class of bugs at parse time.
- **Disambiguation hooks**: When the tool encounters ambiguous patterns (non-deterministic `First`/`Last` aggregation, missing join types, multi-table filter references), it adds specific review instructions instead of just a confidence score.
- **Cleanse macro decoding**: Parses `<Value>` elements inside Cleanse macros to generate specific cleaning code instead of flagging them as raw XML.
- **Learning loop**: Automatically captures migration insights (low-confidence tools, ambiguous patterns, applied fixes) and shares them across your team. On Databricks, lessons are stored in `/Workspace/Shared/alteryx2dbx/lessons.jsonl` so everyone benefits from past migrations. Includes CLI commands: `lessons add`, `lessons list`, `lessons promote`.
- **Plugin system**: Extend the tool with custom handlers, fixes, and validation rules without forking. Plugins are discovered from Python entry points, `.alteryx2dbx.yml` config, or a local `plugins/` directory.
- **Production notebook structure** (v2): `_config.py` with widget parameterization, `_utils.py` with standard helpers, `%run`-based orchestration
- **Smart validation** (v2): Auto-detects join keys from Join/Unique tool configs
- **JSON manifest**: Inspectable intermediate representation between parsing and generation. Edit it, version it, re-generate from it.
- **Fan-out cache hints** (v1): DataFrames used by 2+ downstream tools automatically get `.cache()` appended
- **Syntax validation**: All generated notebooks are compile-checked. Syntax errors are logged as warnings.
- **Network path warnings**: UNC paths (`\\server\...`) in generated code are flagged for migration to DBFS/S3/ADLS
- **Box.com connector support**: Box Input/Output tools generate `boxsdk` code with Databricks Secrets auth
- **Migration documentation**: `document` command generates comprehensive reports with Mermaid diagrams and optional Confluence publishing
- **Batch mode with `--report`**: Aggregate conversion report across multiple workflows
- **Per-workflow conversion report**: Confidence scores per tool with review notes
- **Dual-output routing**: Filter (True/False), Unique (Unique/Duplicates), Join (Join/Left/Right) outputs routed correctly through the DAG

## How It Works

```
.yxmd file
    |
    v
[1. XML Parser]          Parse Alteryx XML into typed dataclasses
    |                     (AlteryxWorkflow, AlteryxTool, AlteryxConnection)
    v
[2. DAG Resolver]         Build dependency graph with NetworkX,
    |                     topological sort for execution order
    v
[3. Handler Dispatch]     Match each tool to its registered handler
    |                     by plugin name or tool type
    v
[4. Expression Transpiler]  Lark grammar parses Alteryx expressions,
    |                       PySparkEmitter transforms the parse tree
    v
[5. Notebook Generator]   Jinja2-free code assembly into Databricks
                          notebook format (.py with # COMMAND ----------
                          cell separators), plus config.yml and report
```

## Limitations

The following are not yet supported:

- **Spatial tools** (Buffer, Spatial Match, Trade Area, etc.)
- **Iterative macros** and **batch macros**
- **Analytic apps** (interface tools, app-level parameters)
- **In-database tools** (In-DB Connect, In-DB Filter, etc.)
- **Predictive/R tools** (Linear Regression, Decision Tree, R Tool)
- **Calgary loader** and **detour/block-until-done** tools
- **Nested macros** (`.yxmc` files referenced from within workflows)

Expressions using unsupported functions are emitted as `# TODO` comments with the original expression preserved.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for dev setup, adding tool handlers, writing plugins, and the lessons-learned workflow. Before accepting generated notebooks, work through [REVIEW_GUIDE.md](./REVIEW_GUIDE.md) — the Alteryx vs Spark behavioral-differences checklist. See [SECURITY_AUDIT.md](./SECURITY_AUDIT.md) for a data-handling and network-egress audit — what the tool sends over the network (nothing, by default), and where raw workflow content ends up on disk.

## License

MIT — see [LICENSE](./LICENSE).
