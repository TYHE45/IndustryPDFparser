from __future__ import annotations

from typing import Any


def metadata_dict(metadata: Any) -> dict[str, Any]:
    return {
        "文件名称": metadata.文件名称,
        "文件类型": metadata.文件类型,
        "文档标题": metadata.文档标题,
        "文档类型": metadata.文档类型,
        "标准编号": metadata.标准编号,
        "版本日期": metadata.版本日期,
        "适用范围": metadata.适用范围,
    }


def metadata_title(metadata: Any) -> str:
    return metadata.文档标题


def metadata_filename(metadata: Any) -> str:
    return metadata.文件名称


def metadata_doc_type(metadata: Any) -> str:
    return metadata.文档类型


def section_dict(section: Any) -> dict[str, Any]:
    return {
        "章节编号": section.章节编号,
        "章节标题": section.章节标题,
        "章节层级": section.章节层级,
        "父章节编号": section.父章节编号,
        "章节清洗文本": section.章节清洗文本,
        "所属部分": section.所属部分,
    }


def section_ref(section: Any) -> str:
    return f"{section.章节编号} {section.章节标题}".strip()


def table_dict(table: Any) -> dict[str, Any]:
    return {
        "表格编号": table.表格编号,
        "表格标题": table.表格标题,
        "所属章节": table.所属章节,
        "表头": table.表头,
        "表体": table.表体,
    }


def table_values(table: Any) -> tuple[str, str, str, list[str], list[list[str]]]:
    return table.表格编号, table.表格标题, table.所属章节, table.表头, table.表体


def parameter_dict(param: Any) -> dict[str, Any]:
    return {
        "参数名称": param.参数名称,
        "参数值清洗值": param.参数值清洗值,
        "参数单位": param.参数单位,
        "参数范围下限": param.参数范围下限,
        "参数范围上限": param.参数范围上限,
        "比较符号": param.比较符号,
        "适用条件": param.适用条件,
        "所属章节": param.所属章节,
        "来源表格": param.来源表格,
        "来源子项": param.来源子项,
        "参数ID": param.参数ID,
        "主体锚点": param.主体锚点.to_dict() if param.主体锚点 else None,
        "来源引用列表": [ref.to_dict() for ref in param.来源引用列表],
        "置信度": param.置信度,
    }


def rule_dict(rule: Any) -> dict[str, Any]:
    return {
        "规则类型": rule.规则类型,
        "规则内容": rule.规则内容,
        "适用条件": rule.适用条件,
        "所属章节": rule.所属章节,
        "规则ID": rule.规则ID,
        "主体锚点": rule.主体锚点.to_dict() if rule.主体锚点 else None,
        "来源引用列表": [ref.to_dict() for ref in rule.来源引用列表],
    }


def inspection_dict(record: Any) -> dict[str, Any]:
    return {
        "检验对象": record.检验对象,
        "检验方法": record.检验方法,
        "检验要求": record.检验要求,
        "证书类型": record.证书类型,
        "所属章节": record.所属章节,
    }


def standard_dict(record: Any) -> dict[str, Any]:
    return {
        "标准编号": record.标准编号,
        "标准名称": record.标准名称,
        "标准类型": record.标准类型,
        "所属章节": record.所属章节,
        "标准族": record.标准族,
        "主体锚点": record.主体锚点.to_dict() if record.主体锚点 else None,
        "来源引用列表": [ref.to_dict() for ref in record.来源引用列表],
    }


def block_dict(block: Any) -> dict[str, Any]:
    return {
        "块类型": block.块类型,
        "标题": block.标题,
        "内容": block.内容,
        "所属部分": block.所属部分,
        "所属章节": block.所属章节,
        "来源页码": block.来源页码,
    }


# --- 兼容函数：返回 tuple 供下游解构 ---

def section_values(section: Any) -> tuple[str, str, int, str, str, str]:
    return (section.章节编号, section.章节标题, section.章节层级,
            section.父章节编号, section.章节清洗文本, section.所属部分)


def block_values(block: Any) -> tuple[str, str, str, str, str, int]:
    return (block.块类型, block.标题, block.内容,
            block.所属部分, block.所属章节, block.来源页码)


def standard_values(record: Any) -> tuple[str, str, str, str]:
    return (record.标准编号, record.标准名称, record.标准类型, record.所属章节)


def parameter_values(param: Any) -> tuple[str, str, str, str, str, str, str, str, str, str]:
    return (param.参数名称, param.参数值清洗值, param.参数单位,
            param.参数范围下限, param.参数范围上限, param.比较符号,
            param.适用条件, param.所属章节, param.来源表格, param.来源子项)


def rule_values(rule: Any) -> tuple[str, str, str, str]:
    return (rule.规则类型, rule.规则内容, rule.适用条件, rule.所属章节)


def inspection_values(record: Any) -> tuple[str, str, str, str, str]:
    return (record.检验对象, record.检验方法, record.检验要求, record.证书类型, record.所属章节)


def metadata_values(metadata: Any) -> tuple[str, str, str, str, str, str, str]:
    return (metadata.文件名称, metadata.文件类型, metadata.文档标题,
            metadata.文档类型, metadata.标准编号, metadata.版本日期, metadata.适用范围)
