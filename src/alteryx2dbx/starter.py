"""Databricks starter notebook template for `alteryx2dbx init`."""

from __future__ import annotations

from pathlib import Path


_TEMPLATE = """# Databricks notebook source
# MAGIC %md
# MAGIC # alteryx2dbx — Starter Notebook
# MAGIC
# MAGIC Convert an Alteryx `.yxmd` / `.yxzp` workflow to a Databricks PySpark notebook.
# MAGIC
# MAGIC **How to use:**
# MAGIC 1. Run the install cell (only needed once per cluster / notebook session).
# MAGIC 2. Fill in the widgets at the top: `workflow_path`, `output_dir`, `mode`.
# MAGIC 3. Run the final cell.
# MAGIC
# MAGIC Inputs live most cleanly in a Unity Catalog Volume (e.g. `/Volumes/<catalog>/<schema>/alteryx/`). Outputs go to your Workspace folder so the generated notebooks can be opened in the Databricks UI.

# COMMAND ----------

# MAGIC %pip install --no-cache-dir --force-reinstall git+https://github.com/aggarwalkartik/alteryx2dbx.git

# COMMAND ----------

# MAGIC %restart_python

# COMMAND ----------

import alteryx2dbx
print(f"alteryx2dbx {alteryx2dbx.__version__}")

# COMMAND ----------

dbutils.widgets.text("workflow_path", "/Volumes/<catalog>/<schema>/alteryx/my_workflow.yxmd", "1. Workflow path (.yxmd / .yxzp)")
dbutils.widgets.text("output_dir", "/Workspace/Users/<you@company.com>/alteryx2dbx_output", "2. Output dir")
dbutils.widgets.dropdown("mode", "convert", ["analyze", "convert", "document"], "3. Mode")

# COMMAND ----------

import subprocess, sys

workflow_path = dbutils.widgets.get("workflow_path")
output_dir = dbutils.widgets.get("output_dir")
mode = dbutils.widgets.get("mode")

if mode == "analyze":
    cmd = ["alteryx2dbx", "analyze", workflow_path]
elif mode == "convert":
    cmd = ["alteryx2dbx", "convert", workflow_path, "-o", output_dir, "--full"]
else:
    cmd = ["alteryx2dbx", "document", workflow_path, "-o", output_dir]

print("Running:", " ".join(cmd))
result = subprocess.run(cmd, capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr, file=sys.stderr)
if result.returncode != 0:
    raise SystemExit(f"alteryx2dbx exited with code {result.returncode}")
"""


def write_starter(path: Path) -> Path:
    """Write the Databricks starter notebook to ``path``. Returns the resolved path."""
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_TEMPLATE, encoding="utf-8")
    return path
