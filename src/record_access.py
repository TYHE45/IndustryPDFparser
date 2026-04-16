from __future__ import annotations

from typing import Any


def metadata_values(metadata: Any) -> tuple[str, str, str, str, str, str, str]:
    return tuple(metadata.__dict__.values())  # type: ignore[return-value]


def metadata_dict(metadata: Any) -> dict[str, Any]:
    filename, extension, title, doc_type, standard_code, version_date, scope = metadata_values(metadata)
    return {
        "文件名称": filename,
        "文件类型": extension,
        "文档标题": title,
        "文档类型": doc_type,
        "标准编号": standard_code,
        "版本日期": version_date,
        "适用范围": scope,
    }


def metadata_title(metadata: Any) -> str:
    return metadata_values(metadata)[2]


def metadata_filename(metadata: Any) -> str:
    return metadata_values(metadata)[0]


def metadata_doc_type(metadata: Any) -> str:
    return metadata_values(metadata)[3]


def section_values(section: Any) -> tuple[str, str, int, str, str, str]:
    return tuple(section.__dict__.values())  # type: ignore[return-value]


def section_dict(section: Any) -> dict[str, Any]:
    number, title, level, parent_number, body, part = section_values(section)
    return {
        "章节编号": number,
        "章节标题": title,
        "章节层级": level,
        "父章节编号": parent_number,
        "章节清洗文本": body,
        "所属部分": part,
    }


def section_ref(section: Any) -> str:
    number, title, *_ = section_values(section)
    return f"{number} {title}".strip()


def table_values(table: Any) -> tuple[str, str, str, list[str], list[list[str]]]:
    return tuple(table.__dict__.values())  # type: ignore[return-value]


def table_dict(table: Any) -> dict[str, Any]:
    table_id, title, section_name, headers, rows = table_values(table)
    return {
        "表格编号": table_id,
        "表格标题": title,
        "所属章节": section_name,
        "表头": headers,
        "表体": rows,
    }


def parameter_values(param: Any) -> tuple[str, str, str, str, str, str, str, str, str, str]:
    return tuple(param.__dict__.values())  # type: ignore[return-value]


def parameter_dict(param: Any) -> dict[str, Any]:
    (
        name,
        value_text,
        unit,
        lower,
        upper,
        comparator,
        condition,
        section_name,
        source_table,
        source_item,
    ) = parameter_values(param)
    return {
        "参数名称": name,
        "参数值清洗值": value_text,
        "参数单位": unit,
        "参数范围下限": lower,
        "参数范围上限": upper,
        "比较符号": comparator,
        "适用条件": condition,
        "所属章节": section_name,
        "来源表格": source_table,
        "来源子项": source_item,
    }


def rule_values(rule: Any) -> tuple[str, str, str, str]:
    return tuple(rule.__dict__.values())  # type: ignore[return-value]


def rule_dict(rule: Any) -> dict[str, Any]:
    rule_type, content, condition, section_name = rule_values(rule)
    return {
        "规则类型": rule_type,
        "规则内容": content,
        "适用条件": condition,
        "所属章节": section_name,
    }


def inspection_values(record: Any) -> tuple[str, str, str, str, str]:
    return tuple(record.__dict__.values())  # type: ignore[return-value]


def inspection_dict(record: Any) -> dict[str, Any]:
    target, method, requirement, certificate, section_name = inspection_values(record)
    return {
        "检验对象": target,
        "检验方法": method,
        "检验要求": requirement,
        "证书类型": certificate,
        "所属章节": section_name,
    }


def standard_values(record: Any) -> tuple[str, str, str, str]:
    return tuple(record.__dict__.values())  # type: ignore[return-value]


def standard_dict(record: Any) -> dict[str, Any]:
    code, title, standard_type, section_name = standard_values(record)
    return {
        "标准编号": code,
        "标准名称": title,
        "标准类型": standard_type,
        "所属章节": section_name,
    }


def block_values(block: Any) -> tuple[str, str, str, str, str, int]:
    return tuple(block.__dict__.values())  # type: ignore[return-value]


def block_dict(block: Any) -> dict[str, Any]:
    block_type, title, content, part_name, section_name, page = block_values(block)
    return {
        "块类型": block_type,
        "标题": title,
        "内容": content,
        "所属部分": part_name,
        "所属章节": section_name,
        "来源页码": page,
    }
