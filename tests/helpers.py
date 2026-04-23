from __future__ import annotations

from src.models import (
    AnchorRef,
    BlockRecord,
    DocumentData,
    DocumentProfile,
    FileMetadata,
    InspectionRecord,
    NumericParameter,
    RuleRecord,
    SectionRecord,
    SourceRef,
    StandardReference,
    StructureNode,
    TableRecord,
)


def build_sample_document() -> DocumentData:
    metadata = FileMetadata(
        文件名称="sample.pdf",
        文件类型="pdf",
        文档标题="示例标准文档",
        文档类型="standard",
        标准编号="SN 544-N",
        版本日期="2024-01",
        适用范围="用于回归测试",
    )
    profile = DocumentProfile(
        文档类型="standard",
        置信度=0.95,
        语言="zh",
        页数=1,
        文本行数=12,
        每页平均字符数=128.0,
        表格数量=1,
    )
    param_anchor = AnchorRef(锚点类型="section", 锚点ID="sec-1", 显示名称="1 范围")
    rule_anchor = AnchorRef(锚点类型="section", 锚点ID="sec-1", 显示名称="1 范围")
    standard_anchor = AnchorRef(锚点类型="section", 锚点ID="sec-1", 显示名称="1 范围")
    source_ref = SourceRef(页码索引=1, 块ID="blk-1", 节点ID="node-1", 摘录文本="测试摘录")
    section = SectionRecord(
        章节编号="1",
        章节标题="范围",
        章节层级=1,
        章节清洗文本="本章节描述标准范围。",
        所属部分="正文",
    )
    table = TableRecord(
        表格编号="表1-第1页",
        表格标题="主要参数",
        所属章节="1 范围",
        表头=["参数", "数值"],
        表体=[["压力", "10"], ["温度", "120"]],
    )
    parameter = NumericParameter(
        参数名称="工作压力",
        参数值清洗值="10",
        参数单位="bar",
        比较符号="=",
        适用条件="常温",
        所属章节="1 范围",
        来源表格="表1-第1页",
        来源子项="压力",
        参数ID="param-1",
        主体锚点=param_anchor,
        来源引用列表=[source_ref],
        置信度=0.91,
    )
    rule = RuleRecord(
        规则类型="约束",
        规则内容="应满足密封要求",
        适用条件="安装后",
        所属章节="1 范围",
        规则ID="rule-1",
        主体锚点=rule_anchor,
        来源引用列表=[source_ref],
    )
    inspection = InspectionRecord(
        检验对象="阀门",
        检验方法="压力测试",
        检验要求="无泄漏",
        证书类型="出厂证书",
        所属章节="1 范围",
    )
    standard = StandardReference(
        标准编号="GB/T 1234-2020",
        标准名称="测试标准",
        标准类型="引用标准",
        所属章节="1 范围",
        标准族="GB",
        主体锚点=standard_anchor,
        来源引用列表=[source_ref],
    )
    block = BlockRecord(
        块类型="paragraph",
        标题="范围",
        内容="这是用于回归测试的正文内容。",
        所属部分="正文",
        所属章节="1 范围",
        来源页码=1,
    )
    node = StructureNode(
        节点ID="node-1",
        节点类型="section",
        节点标题="1 范围",
        节点层级=1,
        起始页码=1,
        结束页码=1,
        关联块ID列表=["blk-1"],
    )
    return DocumentData(
        文件元数据=metadata,
        章节列表=[section],
        表格列表=[table],
        数值参数列表=[parameter],
        规则列表=[rule],
        检验列表=[inspection],
        引用标准列表=[standard],
        内容块列表=[block],
        文档画像=profile,
        结构节点列表=[node],
    )


def build_pipeline_result(*, passed: bool) -> dict[str, object]:
    if passed:
        review = {
            "轮次": 1.0,
            "总分": 95.0,
            "是否通过": True,
            "基础质量分": 35.0,
            "事实正确性分": 38.0,
            "一致性与可追溯性分": 22.0,
            "红线触发": False,
            "红线列表": [],
            "问题清单": [],
            "问题统计": {"严重问题数": 0.0, "重要问题数": 0.0, "一般问题数": 0.0},
            "分项评分": {},
            "文档类型": "standard",
        }
    else:
        review = {
            "轮次": 1.0,
            "总分": 74.0,
            "是否通过": False,
            "基础质量分": 28.0,
            "事实正确性分": 28.0,
            "一致性与可追溯性分": 18.0,
            "红线触发": True,
            "红线列表": [
                {
                    "红线名称": "文本层不足需要OCR",
                    "原因": "文本层不足且未恢复稳定主链。",
                    "分数上限": 74.0,
                }
            ],
            "问题清单": [],
            "问题统计": {"严重问题数": 1.0, "重要问题数": 0.0, "一般问题数": 0.0},
            "分项评分": {},
            "文档类型": "standard",
        }
    return {
        "document": build_sample_document(),
        "markdown": "# 1 范围\n这是用于回归测试的正文内容。",
        "summary": {
            "文档概述": "这是一份用于测试批处理契约的摘要。",
            "_llm_backend": "mock",
        },
        "tags": {
            "主题标签": ["阀门", "标准"],
            "_llm_reason": "mocked",
        },
        "process_log": {
            "输入文件": "sample.pdf",
            "输出目录": "output/test",
            "最终是否通过": review["是否通过"],
            "最终总分": review["总分"],
        },
        "review": review,
        "review_rounds": [
            {
                "轮次": 1.0,
                "阶段": "评审",
                "总分": review["总分"],
                "是否通过": review["是否通过"],
                "红线触发": review["红线触发"],
                "红线列表": review["红线列表"],
                "问题数量": 0,
                "问题统计": review["问题统计"],
                "分项评分": review["分项评分"],
                "问题列表": review["问题清单"],
                "修正动作": [],
            }
        ],
    }


class ImmediateExecutor:
    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)
        return None
