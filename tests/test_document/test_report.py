from alteryx2dbx.parser.xml_parser import parse_yxmd
from alteryx2dbx.document.report import generate_migration_report

SIMPLE_YXMD = """<?xml version="1.0"?>
<AlteryxDocument yxmdVer="2024.1">
  <Properties>
    <MetaInfo>
      <Name>ReportTest</Name>
      <Author>Test Author</Author>
      <Description>Test workflow for report generation</Description>
    </MetaInfo>
  </Properties>
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput">
        <Position x="78" y="78"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <File FileFormat="0">\\\\server\\data\\input.csv</File>
        </Configuration>
        <Annotation DisplayMode="0"><Name>Load Customers</Name></Annotation>
        <MetaInfo connection="Output">
          <RecordInfo>
            <Field name="id" type="Int32"/>
            <Field name="name" size="254" type="V_WString"/>
            <Field name="revenue" type="Double"/>
          </RecordInfo>
        </MetaInfo>
      </Properties>
    </Node>
    <Node ToolID="2">
      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter">
        <Position x="258" y="78"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <Mode>Custom</Mode>
          <Expression>[revenue] &gt; 100</Expression>
        </Configuration>
        <Annotation DisplayMode="0"><Name>High Revenue</Name></Annotation>
        <MetaInfo connection="True">
          <RecordInfo>
            <Field name="id" type="Int32"/>
            <Field name="name" size="254" type="V_WString"/>
            <Field name="revenue" type="Double"/>
          </RecordInfo>
        </MetaInfo>
      </Properties>
    </Node>
    <Node ToolID="3">
      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput">
        <Position x="438" y="78"/>
      </GuiSettings>
      <Properties>
        <Configuration>
          <File FileFormat="0">\\\\server\\output\\result.csv</File>
        </Configuration>
        <Annotation DisplayMode="0"><Name>Write Results</Name></Annotation>
      </Properties>
    </Node>
  </Nodes>
  <Connections>
    <Connection>
      <Origin ToolID="1" Connection="Output"/>
      <Destination ToolID="2" Connection="Input"/>
    </Connection>
    <Connection>
      <Origin ToolID="2" Connection="True"/>
      <Destination ToolID="3" Connection="Input"/>
    </Connection>
  </Connections>
</AlteryxDocument>
"""


def _generate_report(tmp_path):
    wf_file = tmp_path / "report_test.yxmd"
    wf_file.write_text(SIMPLE_YXMD, encoding="utf-8")
    wf = parse_yxmd(wf_file)
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    generate_migration_report(wf, output_dir)
    return (output_dir / "migration_report.md").read_text()


def test_migration_report_generated(tmp_path):
    content = _generate_report(tmp_path)
    assert len(content) > 0


def test_report_has_executive_summary(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Executive Summary" in content
    assert "ReportTest" in content


def test_report_has_data_flow_diagram(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Data Flow Diagram" in content
    assert "```mermaid" in content


def test_report_has_data_sources(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Data Source Inventory" in content
    assert "Load Customers" in content


def test_report_has_output_inventory(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Output Inventory" in content
    assert "Write Results" in content


def test_report_has_business_logic(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Business Logic Summary" in content
    assert "revenue" in content.lower()


def test_report_has_review_checklist(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Manual Review Checklist" in content


def test_report_has_conversion_details(tmp_path):
    content = _generate_report(tmp_path)
    assert "## Conversion Details" in content
    assert "Tool ID" in content
