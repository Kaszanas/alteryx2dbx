"""Parser for Alteryx .yxmd workflow files."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from alteryx2dbx.parser.models import (
    AlteryxConnection,
    AlteryxField,
    AlteryxTool,
    AlteryxWorkflow,
)


def parse_yxmd(path: Path) -> AlteryxWorkflow:
    """Parse a .yxmd file into an AlteryxWorkflow IR model.

    Args:
        path: Path to the .yxmd file.

    Returns:
        Parsed AlteryxWorkflow dataclass.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")

    tree = ET.parse(path)
    root = tree.getroot()

    version = root.get("yxmdVer", "")

    # Parse workflow-level properties
    properties = _parse_properties(root)

    # Extract workflow name from Properties/MetaInfo/Name, fall back to filename
    name = _extract_workflow_name(root, path)

    # Parse tools (nodes)
    tools = _parse_tools(root)

    # Parse connections
    connections = _parse_connections(root)

    return AlteryxWorkflow(
        name=name,
        version=version,
        tools=tools,
        connections=connections,
        properties=properties,
    )


def _extract_workflow_name(root: ET.Element, path: Path) -> str:
    """Extract workflow name from MetaInfo or fall back to filename stem."""
    # Look in Properties/MetaInfo/Name
    meta_name = root.find("./Properties/MetaInfo/Name")
    if meta_name is not None and meta_name.text:
        return meta_name.text
    return path.stem


def _parse_properties(root: ET.Element) -> dict:
    """Parse workflow-level Properties into a dict."""
    props = {}
    props_el = root.find("Properties")
    if props_el is None:
        return props

    for child in props_el:
        if child.tag == "MetaInfo":
            meta = {}
            for meta_child in child:
                meta[meta_child.tag] = meta_child.text or meta_child.get("value", "")
            props["MetaInfo"] = meta
        else:
            # Store simple properties as key: value or key: attribs
            if child.attrib:
                props[child.tag] = dict(child.attrib)
            elif child.text and child.text.strip():
                props[child.tag] = child.text.strip()
            else:
                props[child.tag] = {k: v for k, v in child.attrib.items()} or ""
    return props


def _parse_tools(root: ET.Element) -> dict[int, AlteryxTool]:
    """Parse all Node elements into AlteryxTool dataclasses."""
    tools: dict[int, AlteryxTool] = {}

    for node in root.findall(".//Nodes/Node"):
        tool_id = int(node.get("ToolID", "0"))

        # Skip disabled nodes
        disabled_el = node.find(".//Properties/Disabled")
        if disabled_el is not None and disabled_el.get("value", "False") == "True":
            continue

        # Extract plugin from GuiSettings
        gui_settings = node.find("GuiSettings")
        plugin = gui_settings.get("Plugin", "") if gui_settings is not None else ""

        # Skip ToolContainer nodes (visual-only grouping, no data logic)
        if "ToolContainer" in plugin:
            continue

        # Derive tool_type: last segment of the dotted plugin name.
        # Box plugins are versioned with dots (e.g. "box_input_v1.0.3") and
        # contain no namespace prefix, so rsplit would yield just "3".
        # Detect them by checking whether the last dotted segment looks like a
        # version fragment (all digits) and keep the full string in that case.
        if plugin:
            last = plugin.rsplit(".", 1)[-1]
            tool_type = plugin if last.isdigit() else last
        else:
            tool_type = ""

        # Extract annotation name
        annotation = _extract_annotation(node)

        # Extract config
        config = _extract_config(node, tool_type)

        # Extract output fields from MetaInfo/RecordInfo
        output_fields = _extract_fields(node)

        tools[tool_id] = AlteryxTool(
            tool_id=tool_id,
            plugin=plugin,
            tool_type=tool_type,
            config=config,
            annotation=annotation,
            output_fields=output_fields,
        )

    return tools


def _extract_annotation(node: ET.Element) -> str:
    """Extract the annotation name from a Node element."""
    ann_name = node.find(".//Annotation/Name")
    if ann_name is not None and ann_name.text:
        return ann_name.text
    return ""


def _extract_config(node: ET.Element, tool_type: str) -> dict:
    """Extract tool-specific configuration from a Node's Configuration block."""
    config_el = node.find(".//Configuration")
    if config_el is None:
        return {}

    config: dict = {}

    # Store raw XML for all tools
    config["_raw_xml"] = ET.tostring(config_el, encoding="unicode")

    # Tool-specific extraction
    if tool_type in ("DbFileInput", "DbFileOutput"):
        _extract_file_config(config_el, config)
    elif tool_type == "Filter":
        _extract_filter_config(config_el, config)
    elif tool_type == "Formula":
        _extract_formula_config(config_el, config)
    elif tool_type in ("Join", "FindReplace"):
        _extract_join_config(config_el, config)
    elif tool_type in ("AlteryxSelect", "Select"):
        _extract_select_config(config_el, config)
    elif tool_type == "Summarize":
        _extract_summarize_config(config_el, config)
    elif tool_type == "Sort":
        _extract_sort_config(config_el, config)
    elif tool_type == "DataCleansing":
        _extract_data_cleansing_config(config_el, config)
    elif tool_type == "FindReplace":
        _extract_find_replace_config(config_el, config)
    elif tool_type == "Sample":
        _extract_sample_config(config_el, config)
    elif tool_type == "Unique":
        _extract_unique_config(config_el, config)
    elif tool_type == "CrossTab":
        _extract_cross_tab_config(config_el, config)
    elif tool_type == "Transpose":
        _extract_transpose_config(config_el, config)
    elif tool_type == "RunningTotal":
        _extract_running_total_config(config_el, config)
    elif tool_type == "GenerateRows":
        _extract_generate_rows_config(config_el, config)
    elif tool_type == "Tile":
        _extract_tile_config(config_el, config)
    elif tool_type == "RegEx":
        _extract_regex_config(config_el, config)
    elif tool_type == "TextToColumns":
        _extract_text_to_columns_config(config_el, config)
    elif tool_type == "DateTime":
        _extract_date_time_config(config_el, config)
    elif tool_type == "MultiRowFormula":
        _extract_multi_row_formula_config(config_el, config)
    elif tool_type == "MultiFieldFormula":
        _extract_multi_field_formula_config(config_el, config)
    elif tool_type == "TextInput":
        _extract_text_input_config(config_el, config)
    elif tool_type == "DynamicInput":
        _extract_file_config(config_el, config)
    elif tool_type.startswith("box_input_v") or tool_type.startswith("box_output_v"):
        _extract_box_config(config_el, config)

    return config


def _extract_file_config(config_el: ET.Element, config: dict) -> None:
    """Extract file path and format from DbFileInput/DbFileOutput config."""
    file_el = config_el.find("File")
    if file_el is not None:
        if file_el.text:
            config["file_path"] = file_el.text
        file_format = file_el.get("FileFormat")
        if file_format:
            config["FileFormat"] = file_format


def _extract_filter_config(config_el: ET.Element, config: dict) -> None:
    """Extract filter expression."""
    expr_el = config_el.find("Expression")
    if expr_el is not None and expr_el.text:
        config["expression"] = expr_el.text
    mode_el = config_el.find("Mode")
    if mode_el is not None and mode_el.text:
        config["mode"] = mode_el.text


def _extract_formula_config(config_el: ET.Element, config: dict) -> None:
    """Extract formula fields."""
    fields = []
    for formula_field in config_el.findall(".//FormulaField"):
        fields.append({
            "field": formula_field.get("field", ""),
            "expression": formula_field.get("expression", ""),
            "type": formula_field.get("type", ""),
            "size": formula_field.get("size", ""),
        })
    if fields:
        config["formula_fields"] = fields


def _extract_join_config(config_el: ET.Element, config: dict) -> None:
    """Extract join configuration."""
    join_fields = []
    for join_el in config_el.findall(".//JoinInfo"):
        connection = join_el.get("connection", "")
        for field_el in join_el.findall("Field"):
            left = field_el.get("left", "")
            right = field_el.get("right", "")
            if left and right:
                join_fields.append({"left": left, "right": right})
        # Store connection type (Left/Right indicates which side this JoinInfo describes)
        if connection:
            config["join_connection"] = connection
    if join_fields:
        config["join_fields"] = join_fields
    # Extract join-by-record-position flag
    by_pos = config_el.find("JoinByRecordPos")
    if by_pos is not None:
        config["join_by_position"] = by_pos.get("value", "False") == "True"


def _extract_select_config(config_el: ET.Element, config: dict) -> None:
    """Extract select field configuration."""
    fields = []
    for sf in config_el.findall(".//SelectField"):
        fields.append({
            "field": sf.get("field", ""),
            "selected": sf.get("selected", "True"),
            "rename": sf.get("rename", ""),
            "type": sf.get("type", ""),
            "size": sf.get("size", ""),
        })
    if fields:
        config["select_fields"] = fields


def _extract_summarize_config(config_el: ET.Element, config: dict) -> None:
    """Extract summarize field configuration."""
    fields = []
    for sf in config_el.findall(".//SummarizeField"):
        fields.append({
            "field": sf.get("field", ""),
            "action": sf.get("action", ""),
            "rename": sf.get("rename", ""),
        })
    if fields:
        config["summarize_fields"] = fields


def _extract_sort_config(config_el: ET.Element, config: dict) -> None:
    """Extract sort configuration."""
    fields = []
    # Look specifically inside SortInfo for Field elements
    sort_info = config_el.find("SortInfo")
    if sort_info is not None:
        for sf in sort_info.findall("Field"):
            fields.append({
                "field": sf.get("field", ""),
                "order": sf.get("order", "Ascending"),
            })
    if fields:
        config["sort_fields"] = fields


def _extract_data_cleansing_config(config_el: ET.Element, config: dict) -> None:
    """Extract DataCleansing options and field list."""
    for opt in ("RemoveNull", "RemoveWhitespace", "TrimWhitespace"):
        el = config_el.find(opt)
        if el is not None:
            config[opt] = el.get("value", "True") == "True"

    modify_case_el = config_el.find("ModifyCase")
    if modify_case_el is not None:
        config["ModifyCase"] = modify_case_el.text or modify_case_el.get("value", "")

    fields: list[str] = []
    fields_el = config_el.find("Fields")
    if fields_el is not None:
        for field_el in fields_el.findall("Field"):
            fname = field_el.get("field", "")
            if fname:
                fields.append(fname)
    if fields:
        config["cleansing_fields"] = fields

    # Decode Cleanse macro <Value> elements
    for value_el in config_el.findall(".//Value"):
        name = value_el.get("name", "")
        text = value_el.text or ""
        if name == "ColumnsToCleanse" and text:
            config["macro_columns"] = [c.strip() for c in text.split(",") if c.strip()]
        elif name == "UpperCase":
            config["macro_uppercase"] = text.lower() == "true"
        elif name == "LowerCase":
            config["macro_lowercase"] = text.lower() == "true"
        elif name == "TitleCase":
            config["macro_titlecase"] = text.lower() == "true"
        elif name == "RemoveLeadingTrailingWhitespace":
            config["macro_trim"] = text.lower() == "true"
        elif name == "RemoveTabsLineBreaks":
            config["macro_remove_tabs"] = text.lower() == "true"
        elif name == "RemoveExtraWhitespace":
            config["macro_remove_extra_whitespace"] = text.lower() == "true"


def _extract_find_replace_config(config_el: ET.Element, config: dict) -> None:
    """Extract FindReplace configuration."""
    find_field_el = config_el.find("FindField")
    if find_field_el is not None:
        config["find_field"] = find_field_el.get("field", "")

    replace_field_el = config_el.find("ReplaceField")
    if replace_field_el is not None:
        config["replace_field"] = replace_field_el.get("field", "")

    find_mode_el = config_el.find("FindMode")
    if find_mode_el is not None:
        config["find_mode"] = find_mode_el.text or "Normal"

    # Also extract join fields if present (reuse existing join extraction)
    _extract_join_config(config_el, config)


def _extract_sample_config(config_el: ET.Element, config: dict) -> None:
    """Extract Sample tool configuration."""
    mode_el = config_el.find("Mode")
    if mode_el is not None and mode_el.text:
        config["sample_mode"] = mode_el.text

    n_el = config_el.find("N")
    if n_el is not None and n_el.text:
        try:
            config["sample_n"] = int(n_el.text)
        except ValueError:
            pass

    pct_el = config_el.find("Pct")
    if pct_el is not None and pct_el.text:
        try:
            config["sample_pct"] = float(pct_el.text)
        except ValueError:
            pass


def _extract_unique_config(config_el: ET.Element, config: dict) -> None:
    """Extract Unique tool configuration."""
    fields = []
    for field_el in config_el.findall(".//UniqueFields/Field"):
        fname = field_el.get("field", "")
        if fname:
            fields.append(fname)
    if fields:
        config["unique_fields"] = fields


def _extract_cross_tab_config(config_el: ET.Element, config: dict) -> None:
    """Extract CrossTab configuration."""
    group_fields = []
    for field_el in config_el.findall(".//GroupFields/Field"):
        fname = field_el.get("field", "")
        if fname:
            group_fields.append(fname)
    if group_fields:
        config["ct_group_fields"] = group_fields

    header_el = config_el.find("HeaderField")
    if header_el is not None and header_el.text:
        config["ct_header_field"] = header_el.text

    data_el = config_el.find("DataField")
    if data_el is not None and data_el.text:
        config["ct_data_field"] = data_el.text

    method_el = config_el.find("Method")
    if method_el is not None and method_el.text:
        config["ct_method"] = method_el.text


def _extract_transpose_config(config_el: ET.Element, config: dict) -> None:
    """Extract Transpose configuration."""
    key_fields = []
    for field_el in config_el.findall(".//KeyFields/Field"):
        fname = field_el.get("field", "")
        if fname:
            key_fields.append(fname)
    if key_fields:
        config["tp_key_fields"] = key_fields

    data_fields = []
    for field_el in config_el.findall(".//DataFields/Field"):
        fname = field_el.get("field", "")
        if fname:
            data_fields.append(fname)
    if data_fields:
        config["tp_data_fields"] = data_fields


def _extract_running_total_config(config_el: ET.Element, config: dict) -> None:
    """Extract RunningTotal configuration."""
    running_el = config_el.find("RunningField")
    if running_el is not None and running_el.text:
        config["rt_running_field"] = running_el.text

    group_fields = []
    for field_el in config_el.findall(".//GroupFields/Field"):
        fname = field_el.get("field", "")
        if fname:
            group_fields.append(fname)
    if group_fields:
        config["rt_group_fields"] = group_fields


def _extract_generate_rows_config(config_el: ET.Element, config: dict) -> None:
    """Extract GenerateRows configuration."""
    init_el = config_el.find("InitExpression")
    if init_el is not None and init_el.text:
        config["gr_init"] = init_el.text

    cond_el = config_el.find("ConditionExpression")
    if cond_el is not None and cond_el.text:
        config["gr_condition"] = cond_el.text

    loop_el = config_el.find("LoopExpression")
    if loop_el is not None and loop_el.text:
        config["gr_loop"] = loop_el.text


def _extract_tile_config(config_el: ET.Element, config: dict) -> None:
    """Extract Tile configuration."""
    method_el = config_el.find("Method")
    if method_el is not None and method_el.text:
        config["tile_method"] = method_el.text

    num_el = config_el.find("NumTiles")
    if num_el is not None and num_el.text:
        try:
            config["tile_num"] = int(num_el.text)
        except ValueError:
            pass

    field_el = config_el.find("Field")
    if field_el is not None and field_el.text:
        config["tile_field"] = field_el.text


def _extract_regex_config(config_el: ET.Element, config: dict) -> None:
    """Extract RegEx configuration."""
    field_el = config_el.find("Field")
    if field_el is not None and field_el.text:
        config["rx_field"] = field_el.text

    # Try both RegExExpression and Expression tags
    expr_el = config_el.find("RegExExpression")
    if expr_el is None:
        expr_el = config_el.find("Expression")
    if expr_el is not None and expr_el.text:
        config["rx_expression"] = expr_el.text

    mode_el = config_el.find("Mode")
    if mode_el is not None and mode_el.text:
        config["rx_mode"] = mode_el.text

    replace_el = config_el.find("ReplaceExpression")
    if replace_el is not None and replace_el.text:
        config["rx_replace"] = replace_el.text

    output_fields = []
    for of_el in config_el.findall(".//OutputFields/Field"):
        fname = of_el.get("field", "")
        if fname:
            output_fields.append(fname)
    if output_fields:
        config["rx_output_fields"] = output_fields


def _extract_text_to_columns_config(config_el: ET.Element, config: dict) -> None:
    """Extract TextToColumns configuration."""
    field_el = config_el.find("Field")
    if field_el is not None and field_el.text:
        config["ttc_field"] = field_el.text

    delim_el = config_el.find("Delimiter")
    if delim_el is not None and delim_el.text:
        config["ttc_delimiter"] = delim_el.text

    num_el = config_el.find("NumFields")
    if num_el is not None and num_el.text:
        try:
            config["ttc_num_columns"] = int(num_el.text)
        except ValueError:
            pass

    split_el = config_el.find("SplitToRows")
    if split_el is not None:
        config["ttc_split_to_rows"] = split_el.text == "True" or split_el.get("value", "False") == "True"

    root_name_el = config_el.find("RootName")
    if root_name_el is not None and root_name_el.text:
        config["ttc_root_name"] = root_name_el.text


def _extract_date_time_config(config_el: ET.Element, config: dict) -> None:
    """Extract DateTime configuration."""
    field_el = config_el.find("Field")
    if field_el is not None and field_el.text:
        config["dt_field"] = field_el.text

    fmt_in_el = config_el.find("FormatIn")
    if fmt_in_el is None:
        fmt_in_el = config_el.find("Format")
    if fmt_in_el is not None and fmt_in_el.text:
        config["dt_format_in"] = fmt_in_el.text

    fmt_out_el = config_el.find("FormatOut")
    if fmt_out_el is None:
        fmt_out_el = config_el.find("Format")
    if fmt_out_el is not None and fmt_out_el.text:
        config["dt_format_out"] = fmt_out_el.text

    conv_el = config_el.find("Conversion")
    if conv_el is not None and conv_el.text:
        config["dt_conversion"] = conv_el.text


def _extract_multi_row_formula_config(config_el: ET.Element, config: dict) -> None:
    """Extract MultiRowFormula configuration."""
    expr_el = config_el.find("Expression")
    if expr_el is not None and expr_el.text:
        config["mrf_expression"] = expr_el.text

    field_el = config_el.find("Field")
    if field_el is not None and field_el.text:
        config["mrf_field"] = field_el.text

    group_fields = []
    for gf_el in config_el.findall(".//GroupByFields/Field"):
        fname = gf_el.get("field", "")
        if fname:
            group_fields.append(fname)
    if group_fields:
        config["mrf_group_fields"] = group_fields

    num_rows_el = config_el.find("NumRows")
    if num_rows_el is not None and num_rows_el.text:
        config["mrf_num_rows"] = num_rows_el.text


def _extract_multi_field_formula_config(config_el: ET.Element, config: dict) -> None:
    """Extract MultiFieldFormula configuration."""
    expr_el = config_el.find("Expression")
    if expr_el is not None and expr_el.text:
        config["mff_expression"] = expr_el.text

    fields = []
    for field_el in config_el.findall(".//Fields/Field"):
        fname = field_el.get("field", "")
        if fname:
            fields.append(fname)
    if fields:
        config["mff_fields"] = fields


def _extract_text_input_config(config_el: ET.Element, config: dict) -> None:
    """Extract TextInput inline data (fields + rows)."""
    fields_el = config_el.find("Fields")
    if fields_el is not None:
        config["ti_fields"] = [f.get("name", "") for f in fields_el.findall("Field")]

    data: list[list[str]] = []
    data_el = config_el.find("Data")
    if data_el is not None:
        for row in data_el.findall("r"):
            row_data = []
            for cell in row.findall("c"):
                row_data.append(cell.text or "")
            data.append(row_data)
    config["ti_data"] = data


def _extract_box_config(config_el: ET.Element, config: dict) -> None:
    """Extract Box.com connector configuration."""
    _simple_fields = {
        "FilePath": "file_path",
        "boxFileId": "box_file_id",
        "boxParentId": "box_parent_id",
        "fileName": "file_name",
        "FileFormat": "file_format",
        "authType": "auth_type",
        "Delimiter": "delimiter",
        "ExistingFileBehavior": "existing_file_behavior",
    }
    for xml_name, config_key in _simple_fields.items():
        el = config_el.find(xml_name)
        if el is not None and el.text:
            config[config_key] = el.text

    header_el = config_el.find("DelimitedHasHeader")
    if header_el is not None and header_el.text:
        config["has_header"] = header_el.text.lower() == "true"

    sheet_el = config_el.find("ExcelSheetNameValues")
    if sheet_el is not None and sheet_el.text:
        config["excel_sheet"] = sheet_el.text


def _extract_fields(node: ET.Element) -> list[AlteryxField]:
    """Extract output fields from MetaInfo/RecordInfo."""
    fields: list[AlteryxField] = []
    for meta_info in node.findall(".//MetaInfo"):
        for field_el in meta_info.findall(".//RecordInfo/Field"):
            name = field_el.get("name", "")
            ftype = field_el.get("type", "")
            size_str = field_el.get("size")
            scale_str = field_el.get("scale")
            fields.append(AlteryxField(
                name=name,
                type=ftype,
                size=int(size_str) if size_str else None,
                scale=int(scale_str) if scale_str else None,
            ))
    return fields


def _parse_connections(root: ET.Element) -> list[AlteryxConnection]:
    """Parse all Connection elements into AlteryxConnection dataclasses."""
    connections: list[AlteryxConnection] = []

    for conn in root.findall(".//Connections/Connection"):
        origin = conn.find("Origin")
        dest = conn.find("Destination")
        if origin is not None and dest is not None:
            connections.append(AlteryxConnection(
                source_tool_id=int(origin.get("ToolID", "0")),
                source_anchor=origin.get("Connection", ""),
                target_tool_id=int(dest.get("ToolID", "0")),
                target_anchor=dest.get("Connection", ""),
            ))

    return connections
