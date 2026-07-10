from alteryx2dbx.parser.xml_parser import parse_yxmd

BOX_INPUT_YXMD = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Properties><MetaInfo><Name>BoxTest</Name></MetaInfo></Properties>
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="box_input_v1.0.3">
        <Position x="78" y="78"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <authType>ServicePrincipal</authType>
          <FilePath>/reports/monthly/sales.csv</FilePath>
          <boxFileId>123456789</boxFileId>
          <boxParentId>987654321</boxParentId>
          <fileName>sales.csv</fileName>
          <FileFormat>Delimited</FileFormat>
          <DelimitedHasHeader>True</DelimitedHasHeader>
          <Delimiter>COMMA</Delimiter>
        </Configuration>
        <Annotation DisplayMode="0">
          <Name>Box Sales Data</Name>
        </Annotation>
      </Properties>
    </Node>
  </Nodes>
  <Connections></Connections>
</AlteryxDocument>
"""

BOX_OUTPUT_YXMD = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Properties><MetaInfo><Name>BoxOutputTest</Name></MetaInfo></Properties>
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="box_output_v1.0.3">
        <Position x="78" y="78"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <authType>EndUser</authType>
          <FilePath>/reports/output/results.xlsx</FilePath>
          <boxFileId>111222333</boxFileId>
          <boxParentId>444555666</boxParentId>
          <fileName>results.xlsx</fileName>
          <FileFormat>Excel</FileFormat>
          <ExcelSheetNameValues>Sheet1</ExcelSheetNameValues>
          <ExistingFileBehavior>Overwrite</ExistingFileBehavior>
        </Configuration>
        <Annotation DisplayMode="0">
          <Name>Box Output Results</Name>
        </Annotation>
      </Properties>
    </Node>
  </Nodes>
  <Connections></Connections>
</AlteryxDocument>
"""


def test_box_input_config_extraction(tmp_path):
    wf_file = tmp_path / "box_test.yxmd"
    wf_file.write_text(BOX_INPUT_YXMD, encoding="utf-8")
    wf = parse_yxmd(wf_file)
    tool = wf.tools[1]
    assert tool.tool_type == "box_input_v1.0.3"
    assert tool.config["box_file_id"] == "123456789"
    assert tool.config["box_parent_id"] == "987654321"
    assert tool.config["file_name"] == "sales.csv"
    assert tool.config["file_format"] == "Delimited"
    assert tool.config["auth_type"] == "ServicePrincipal"
    assert tool.config["has_header"] is True
    assert tool.config["delimiter"] == "COMMA"
    assert tool.config["file_path"] == "/reports/monthly/sales.csv"


def test_box_output_config_extraction(tmp_path):
    wf_file = tmp_path / "box_out_test.yxmd"
    wf_file.write_text(BOX_OUTPUT_YXMD, encoding="utf-8")
    wf = parse_yxmd(wf_file)
    tool = wf.tools[1]
    assert tool.tool_type == "box_output_v1.0.3"
    assert tool.config["box_file_id"] == "111222333"
    assert tool.config["file_format"] == "Excel"
    assert tool.config["excel_sheet"] == "Sheet1"
    assert tool.config["existing_file_behavior"] == "Overwrite"
    assert tool.config["auth_type"] == "EndUser"
