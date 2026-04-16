from __future__ import annotations

from dataclasses import replace
from typing import Any

from config import AppConfig
from src.llm_refiner import refine_document_structure
from src.md_builder import build_markdown
from src.normalizer import normalize_document
from src.parser import PDFParser
from src.reviewer import review_outputs
from src.summarizer import build_summary
from src.tagger import build_tags

ROUND_NO = "\u8f6e\u6b21"
STAGE = "\u9636\u6bb5"
FINAL_STAGE = "\u6700\u7ec8\u751f\u6210\u4e0e\u9a8c\u6536"
SECTION_COUNT = "\u7ae0\u8282\u6570\u91cf"
TABLE_COUNT = "\u8868\u683c\u6570\u91cf"
NUMERIC_PARAM_COUNT = "\u6570\u503c\u578b\u53c2\u6570\u6570\u91cf"
RULE_COUNT = "\u89c4\u5219\u6570\u91cf"
LLM_REFINE_STAGE = "LLM\u7ed3\u6784\u590d\u6838"


def run_iterative_pipeline(config: AppConfig) -> dict[str, object]:
    parser = PDFParser(config)
    document = normalize_document(parser.parse())
    document, refinement_rounds = refine_document_structure(document, config)

    output_config = config
    llm_round_count = sum(1 for item in refinement_rounds if item.get(STAGE) == LLM_REFINE_STAGE)
    llm_refine_failed = any(item.get(STAGE) == LLM_REFINE_STAGE and item.get("\u662f\u5426\u6210\u529f") is False for item in refinement_rounds)
    if llm_refine_failed:
        output_config = replace(config, use_llm=False)

    markdown = build_markdown(document)
    summary = build_summary(document, output_config)
    tags = build_tags(document, output_config)
    review = review_outputs(document, markdown, summary, tags)

    rounds: list[dict[str, Any]] = list(refinement_rounds)
    rounds.append(
        {
            ROUND_NO: float(len(refinement_rounds) + 1),
            STAGE: FINAL_STAGE,
            SECTION_COUNT: float(len(document.sections)),
            TABLE_COUNT: float(len(document.tables)),
            NUMERIC_PARAM_COUNT: float(len(document.numeric_parameters)),
            RULE_COUNT: float(len(document.rules)),
        }
    )

    profile = getattr(document, "profile", None)
    process_log = {
        "\u8f93\u5165\u6587\u4ef6": str(config.input_path),
        "\u8f93\u51fa\u76ee\u5f55": str(config.output_dir),
        "\u662f\u5426\u8c03\u7528LLM": config.use_llm,
        "LLM\u7ed3\u6784\u4fee\u6b63\u8f6e\u6b21": float(llm_round_count),
        "summary_LLM\u540e\u7aef": summary.get("_llm_backend", ""),
        "tags_LLM\u540e\u7aef": tags.get("_llm_backend", ""),
        "\u6587\u6863\u7c7b\u578b": getattr(profile, "doc_type", "unknown"),
        "\u753b\u50cf\u7f6e\u4fe1\u5ea6": getattr(profile, "confidence", 0.0),
        SECTION_COUNT: len(document.sections),
        TABLE_COUNT: len(document.tables),
        NUMERIC_PARAM_COUNT: len(document.numeric_parameters),
        RULE_COUNT: len(document.rules),
        "\u68c0\u9a8c\u8bb0\u5f55\u6570\u91cf": len(document.inspections),
        "\u5f15\u7528\u6807\u51c6\u6570\u91cf": len(document.standards),
        "\u8fed\u4ee3\u8f6e\u6b21": float(len(rounds)),
    }

    return {
        "document": document,
        "markdown": markdown,
        "summary": summary,
        "tags": tags,
        "review": review,
        "rounds": rounds,
        "process_log": process_log,
    }
