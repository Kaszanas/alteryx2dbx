from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.registry import get_handler
import alteryx2dbx.handlers  # noqa: F401


def _make_box_output_tool(
    tool_id=5,
    file_format="Delimited",
    file_name="output.csv",
    box_parent_id="444555666",
    existing_behavior="Overwrite",
):
    return AlteryxTool(
        tool_id=tool_id,
        plugin="box_output_v1.0.3",
        tool_type="box_output_v1.0.3",
        config={
            "box_file_id": "111222333",
            "box_parent_id": box_parent_id,
            "file_name": file_name,
            "file_format": file_format,
            "file_path": f"/reports/output/{file_name}",
            "auth_type": "ServicePrincipal",
            "existing_file_behavior": existing_behavior,
            "_raw_xml": "<Configuration/>",
        },
        annotation="Box Output Results",
        output_fields=[],
    )


def test_box_output_csv():
    tool = _make_box_output_tool()
    step = get_handler(tool).convert(tool, input_df_names=["df_4"])
    assert "toPandas()" in step.code
    assert "to_csv" in step.code
    assert (
        "upload_stream" in step.code
        or "update_contents_with_stream" in step.code
    )
    assert step.confidence == 0.7
    assert step.input_dfs == ["df_4"]
    assert step.output_df == "df_5"


def test_box_output_excel():
    tool = _make_box_output_tool(file_format="Excel", file_name="out.xlsx")
    step = get_handler(tool).convert(tool, input_df_names=["df_4"])
    assert "to_excel" in step.code


def test_box_output_json():
    tool = _make_box_output_tool(file_format="JSON", file_name="out.json")
    step = get_handler(tool).convert(tool, input_df_names=["df_4"])
    assert "to_json" in step.code


def test_box_output_abort_behavior():
    tool = _make_box_output_tool(existing_behavior="Abort")
    step = get_handler(tool).convert(tool, input_df_names=["df_4"])
    assert "TODO" in step.code or "Abort" in step.code


def test_box_output_overwrite():
    tool = _make_box_output_tool(existing_behavior="Overwrite")
    step = get_handler(tool).convert(tool, input_df_names=["df_4"])
    assert "update_contents_with_stream" in step.code
