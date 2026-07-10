from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.input_data import InputDataHandler


def _make_tool(**overrides):
    defaults = dict(
        tool_id=1,
        plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
        tool_type="DbFileInput",
        config={
            "File": r"C:\Data\sales.csv",
            "FormatType": "0",
            "HeaderRow": "true",
        },
        annotation="Read Sales CSV",
    )
    defaults.update(overrides)
    return AlteryxTool(**defaults)


def test_csv_input():
    tool = _make_tool()
    handler = InputDataHandler()
    step = handler.convert(tool)

    assert step.output_df == "df_1"
    assert 'format("csv")' in step.code
    assert "spark.read" in step.code
    assert '"header", "true"' in step.code
    assert "inferSchema" in step.code
    assert "TODO: Update the file path" in step.code
    assert step.confidence == 0.9
    assert step.input_dfs == []


def test_excel_input():
    tool = _make_tool(
        tool_id=5,
        config={
            "File": r"C:\Data\report.xlsx",
            "FormatType": "19",
            "HeaderRow": "true",
            "Sheet": "DataSheet",
        },
        annotation="Read Excel Report",
    )
    handler = InputDataHandler()
    step = handler.convert(tool)

    assert step.output_df == "df_5"
    assert "com.crealytics.spark.excel" in step.code
    assert "DataSheet" in step.code
    assert "spark.read" in step.code
    assert any(
        "excel" in n.lower() or "crealytics" in n.lower() for n in step.notes
    )


def test_parquet_input():
    tool = _make_tool(
        tool_id=10,
        config={
            "File": r"C:\Data\warehouse.parquet",
            "FormatType": "25",
        },
        annotation="Read Parquet",
    )
    handler = InputDataHandler()
    step = handler.convert(tool)

    assert step.output_df == "df_10"
    assert "spark.read.parquet" in step.code
    assert "warehouse.parquet" in step.code


def test_output_df_name_uses_tool_id():
    tool = _make_tool(tool_id=42)
    handler = InputDataHandler()
    step = handler.convert(tool)
    assert step.output_df == "df_42"


def test_notes_include_source_format():
    tool = _make_tool()
    handler = InputDataHandler()
    step = handler.convert(tool)
    assert any("csv" in n.lower() for n in step.notes)


def test_default_format_is_csv():
    tool = _make_tool(config={"File": "data.txt"})
    handler = InputDataHandler()
    step = handler.convert(tool)
    assert 'format("csv")' in step.code
