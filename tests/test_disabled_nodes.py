"""Tests for Task 10: Disabled node detection and ToolContainer skipping."""

import xml.etree.ElementTree as ET

from alteryx2dbx.parser.xml_parser import _parse_tools


def _make_root_xml(nodes_xml: str) -> ET.Element:
    """Build a minimal Alteryx XML root with the given <Node> elements."""
    xml = f"""<AlteryxDocument yxmdVer="2024.1">
  <Nodes>{nodes_xml}</Nodes>
</AlteryxDocument>"""
    return ET.fromstring(xml)


class TestDisabledNodeSkipping:
    def test_disabled_node_excluded(self):
        root = _make_root_xml("""
            <Node ToolID="1">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Filter" />
                <Properties><Disabled value="True" /></Properties>
            </Node>
            <Node ToolID="2">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Sort" />
            </Node>
        """)
        tools = _parse_tools(root)
        assert 1 not in tools
        assert 2 in tools

    def test_enabled_node_included(self):
        root = _make_root_xml("""
            <Node ToolID="1">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Filter" />
                <Properties><Disabled value="False" /></Properties>
            </Node>
        """)
        tools = _parse_tools(root)
        assert 1 in tools

    def test_no_disabled_element_included(self):
        root = _make_root_xml("""
            <Node ToolID="1">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Filter" />
            </Node>
        """)
        tools = _parse_tools(root)
        assert 1 in tools


class TestToolContainerSkipping:
    def test_tool_container_excluded(self):
        root = _make_root_xml("""
            <Node ToolID="1">
                <GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer" />
            </Node>
            <Node ToolID="2">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Filter" />
            </Node>
        """)
        tools = _parse_tools(root)
        assert 1 not in tools
        assert 2 in tools

    def test_non_container_included(self):
        root = _make_root_xml("""
            <Node ToolID="1">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Formula" />
            </Node>
        """)
        tools = _parse_tools(root)
        assert 1 in tools


class TestTextBoxSkipping:
    def test_text_box_excluded(self):
        root = _make_root_xml("""
            <Node ToolID="1">
                <GuiSettings Plugin="AlteryxGuiToolkit.TextBox.TextBox" />
            </Node>
            <Node ToolID="2">
                <GuiSettings Plugin="AlteryxBasePluginsEngine.Filter" />
            </Node>
        """)
        tools = _parse_tools(root)
        assert 1 not in tools
        assert 2 in tools
