from alteryx2dbx.parser.models import AlteryxTool
from alteryx2dbx.handlers.registry import get_handler
import alteryx2dbx.handlers  # noqa: F401


def _make_box_input_tool(
    tool_id=1,
    file_format="Delimited",
    box_file_id="123456789",
    file_name="sales.csv",
    has_header=True,
    delimiter="COMMA",
    excel_sheet=None,
):
    config = {
        "box_file_id": box_file_id,
        "box_parent_id": "987654321",
        "file_name": file_name,
        "file_format": file_format,
        "file_path": f"/reports/{file_name}",
        "auth_type": "ServicePrincipal",
        "has_header": has_header,
        "delimiter": delimiter,
        "_raw_xml": "<Configuration/>",
    }
    if excel_sheet:
        config["excel_sheet"] = excel_sheet
    return AlteryxTool(
        tool_id=tool_id,
        plugin="box_input_v1.0.3",
        tool_type="box_input_v1.0.3",
        config=config,
        annotation="Box Sales Data",
        output_fields=[],
    )


def test_box_input_csv():
    tool = _make_box_input_tool()
    handler = get_handler(tool)
    step = handler.convert(tool)
    assert "box_client.file" in step.code
    assert "123456789" in step.code
    assert "pd.read_csv" in step.code
    assert step.confidence == 0.8
    assert step.output_df == "df_1"


def test_box_input_excel():
    tool = _make_box_input_tool(
        file_format="Excel", file_name="data.xlsx", excel_sheet="Sheet1"
    )
    step = get_handler(tool).convert(tool)
    assert "pd.read_excel" in step.code
    assert "Sheet1" in step.code


def test_box_input_json():
    tool = _make_box_input_tool(file_format="JSON", file_name="data.json")
    step = get_handler(tool).convert(tool)
    assert "pd.read_json" in step.code


def test_box_input_avro_unsupported():
    tool = _make_box_input_tool(file_format="Avro", file_name="data.avro")
    step = get_handler(tool).convert(tool)
    assert "TODO" in step.code
    assert step.confidence < 0.8


def test_box_input_delimiter_tab():
    tool = _make_box_input_tool(delimiter="TAB")
    step = get_handler(tool).convert(tool)
    assert "\\t" in step.code


def test_box_input_no_header():
    tool = _make_box_input_tool(has_header=False)
    step = get_handler(tool).convert(tool)
    assert "header=False" in step.code or "header=None" in step.code
