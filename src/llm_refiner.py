from __future__ import annotations

import copy
import re
from dataclasses import fields
from typing import Any

from config import AppConfig
from src.models import DocumentData
from src.normalizer import normalize_document
from src.openai_compat import llm_available, request_structured_json
from src.record_access import block_values, metadata_dict, section_ref, section_values
from src.utils import normalize_line

ROUND_NO = "\u8f6e\u6b21"
STAGE = "\u9636\u6bb5"
LOCAL_STAGE = "\u672c\u5730\u9884\u6e05\u7406"
LLM_STAGE = "LLM\u7ed3\u6784\u590d\u6838"
CANDIDATE_SECTION_COUNT = "\u5019\u9009\u8282\u6570"
CANDIDATE_BLOCK_COUNT = "\u5019\u9009\u5757\u6570"
SUCCESS = "\u662f\u5426\u6210\u529f"
CHANGED = "\u662f\u5426\u6709\u6539\u52a8"
ACTION_COUNT = "\u6267\u884c\u52a8\u4f5c\u6570"
ERROR = "\u9519\u8bef"
LLM_BACKEND = "LLM\u540e\u7aef"
GLOBAL_NOTES = "\u5168\u5c40\u8bf4\u660e"
TITLE_BLOCK = "\u6807\u9898"
BODY_BLOCK = "\u6b63\u6587"
TABLE_FRAGMENT_BLOCK = "\u8868\u683c\u788e\u7247"

MONTH_YEAR_RE = re.compile(
    r"^(?:"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"januar|februar|m\u00e4rz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember"
    r")\s+\d{4}$",
    re.IGNORECASE,
)
PAGE_NOISE_RE = re.compile(r"^(?:page|seite|supersedes|contents|index)$", re.IGNORECASE)
PURE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*$")
ICS_RE = re.compile(r"^ICS\s+\d+(?:\.\d+)*$", re.IGNORECASE)
DIMENSION_CODE_RE = re.compile(r"^(?:G|R|DN)\s*\d+(?:\s+\d+/\d+)?$", re.IGNORECASE)
COPYRIGHT_RE = re.compile(r"^(?:\u00a9|copyright\b|all rights reserved\b)", re.IGNORECASE)
NOISE_MARKER_RE = re.compile(r"^(?:bearbeitet|edited|draft|status)$", re.IGNORECASE)
SPLIT_TOKEN_RE = re.compile(r"^[A-Z](?:\s*/\s*[A-Z])+(?:\s*/\s*[A-Z])*$")
TRAILING_FRAGMENT_RE = re.compile(r"^[a-z(].*[.;]?$")
UNIT_FRAGMENT_RE = re.compile(r"^(?:mm|cm|m|bar|psi|kg|g|\u00b0c|\u2103|%|a/m)$", re.IGNORECASE)
MATRIX_FRAGMENT_RE = re.compile(r"^(?:[A-Z0-9]+\s*/\s*)+[A-Z0-9.]+$")
REPEATED_NUMBER_FRAGMENT_RE = re.compile(r"^(?:\d+[.,]?\d*\s*){3,}$")
SHORT_TOKEN_RE = re.compile(r"^[A-Z]{1,3}$")
LETTER_RANGE_RE = re.compile(r"^[A-Z](?:\s*-\s*[A-Z])+$")
VALUE_FRAGMENT_RE = re.compile(r"^(?:[+\-]|≤|≥|<|>)?\s*(?:DN\s*)?\d+(?:[.,]\d+)?\s*%?$", re.IGNORECASE)
LEADING_CONJUNCTION_RE = re.compile(r"^(?:and|und|or|oder)\b", re.IGNORECASE)
SENTENCE_VERB_RE = re.compile(r"\b(?:beträgt|ist|sind|muss|müssen|werden|wird|can|shall|must|used|pointing|given)\b", re.IGNORECASE)


def refine_document_structure(document: DocumentData, config: AppConfig) -> tuple[DocumentData, list[dict[str, Any]]]:
    refined = copy.deepcopy(document)
    rounds: list[dict[str, Any]] = []

    local_changed, local_actions, local_section_count, local_block_count = _apply_local_cleanup(refined)
    rounds.append(
        {
            ROUND_NO: 0.0,
            STAGE: LOCAL_STAGE,
            CANDIDATE_SECTION_COUNT: float(local_section_count),
            CANDIDATE_BLOCK_COUNT: float(local_block_count),
            SUCCESS: True,
            CHANGED: local_changed,
            ACTION_COUNT: float(local_actions),
        }
    )
    if local_changed:
        _reset_views(refined)
        refined = normalize_document(refined)

    if not (config.use_llm and llm_available()):
        return refined, rounds

    for round_index in range(1, max(1, config.llm_structure_refine_rounds) + 1):
        section_candidates = _collect_suspicious_sections(refined, limit=max(1, config.llm_structure_refine_candidates))
        block_candidates = _collect_suspicious_blocks(refined, limit=max(1, config.llm_structure_refine_candidates))
        if not section_candidates and not block_candidates:
            break

        try:
            response, backend = _request_refinement(refined, section_candidates, block_candidates, config)
        except Exception as exc:
            rounds.append(
                {
                    ROUND_NO: float(round_index),
                    STAGE: LLM_STAGE,
                    CANDIDATE_SECTION_COUNT: float(len(section_candidates)),
                    CANDIDATE_BLOCK_COUNT: float(len(block_candidates)),
                    SUCCESS: False,
                    ERROR: str(exc),
                }
            )
            break

        changed, action_count = _apply_refinement(refined, section_candidates, block_candidates, response)
        rounds.append(
            {
                ROUND_NO: float(round_index),
                STAGE: LLM_STAGE,
                CANDIDATE_SECTION_COUNT: float(len(section_candidates)),
                CANDIDATE_BLOCK_COUNT: float(len(block_candidates)),
                SUCCESS: True,
                LLM_BACKEND: backend,
                CHANGED: changed,
                ACTION_COUNT: float(action_count),
                GLOBAL_NOTES: response.get("global_notes", []),
            }
        )
        if not changed:
            break

        _reset_views(refined)
        refined = normalize_document(refined)

    return refined, rounds


def _apply_local_cleanup(document: DocumentData) -> tuple[bool, int, int, int]:
    section_candidates = _collect_suspicious_sections(document, limit=10_000)
    block_candidates = _collect_suspicious_blocks(document, limit=10_000)

    changed = False
    action_count = 0

    section_actions: list[tuple[int, str]] = []
    for item in section_candidates:
        reasons = set(item["reasons"])
        if not reasons.intersection(_hard_heading_reasons()):
            continue
        direction = "previous"
        if item["section_index"] == 0:
            direction = "next"
        elif item["body_line_count"] > 4 and item["section_index"] + 1 < len(document.sections):
            direction = "next"
        section_actions.append((item["section_index"], direction))

    for section_index, direction in sorted(section_actions, key=lambda pair: pair[0], reverse=True):
        if _merge_section(document, section_index, direction):
            changed = True
            action_count += 1

    block_delete_indexes: list[int] = []
    block_to_body_indexes: list[int] = []
    for item in block_candidates:
        reasons = set(item["reasons"])
        block_type = item["block_type"]
        if block_type == TABLE_FRAGMENT_BLOCK and reasons.intersection(_hard_block_reasons()):
            block_delete_indexes.append(item["block_index"])
        elif block_type == TITLE_BLOCK and reasons.intersection({"sentence_fragment", "lowercase_fragment", "too_short_for_heading"}):
            block_to_body_indexes.append(item["block_index"])

    for block_index in sorted(set(block_delete_indexes), reverse=True):
        if 0 <= block_index < len(document.blocks):
            del document.blocks[block_index]
            changed = True
            action_count += 1

    for block_index in sorted(set(block_to_body_indexes)):
        if 0 <= block_index < len(document.blocks):
            block = document.blocks[block_index]
            if normalize_line(_get_field(block, 0)) == TITLE_BLOCK:
                title = normalize_line(_get_field(block, 1))
                content = normalize_line(_get_field(block, 2))
                merged = "\n".join([line for line in [title, content] if line])
                _set_field(block, 0, BODY_BLOCK)
                _set_field(block, 1, "")
                _set_field(block, 2, merged)
                changed = True
                action_count += 1

    return changed, action_count, len(section_candidates), len(block_candidates)


def _collect_suspicious_sections(document: DocumentData, limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    sections = document.sections
    for idx, section in enumerate(sections):
        number, title, _, _, body, _ = section_values(section)
        normalized_title = normalize_line(title)
        normalized_body = normalize_line(body)
        reasons = _suspicious_heading_reasons(normalized_title, normalized_body, number)
        if not reasons:
            continue

        prev_ref = section_ref(sections[idx - 1]) if idx > 0 else ""
        next_ref = section_ref(sections[idx + 1]) if idx + 1 < len(sections) else ""
        body_lines = [normalize_line(line) for line in str(body).splitlines() if normalize_line(line)]
        candidates.append(
            {
                "candidate_id": f"sec-{idx}",
                "kind": "section",
                "section_index": idx,
                "section_number": normalize_line(number),
                "section_title": normalized_title,
                "section_ref": section_ref(section),
                "body_line_count": len(body_lines),
                "body_excerpt": " ".join(body_lines[:3])[:240],
                "previous_section": normalize_line(prev_ref),
                "next_section": normalize_line(next_ref),
                "reasons": reasons,
                "score": len(reasons),
            }
        )

    candidates.sort(key=lambda item: (-item["score"], item["section_index"]))
    return candidates[:limit]


def _collect_suspicious_blocks(document: DocumentData, limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for idx, block in enumerate(document.blocks):
        block_type, title, content, _, section_name, page = block_values(block)
        block_type = normalize_line(block_type)
        title = normalize_line(title)
        content = normalize_line(content)
        reasons = _suspicious_fragment_reasons(block_type, title, content)
        if not reasons:
            continue
        candidates.append(
            {
                "candidate_id": f"blk-{idx}",
                "kind": "block",
                "block_index": idx,
                "block_type": block_type,
                "title": title,
                "content_excerpt": content[:240],
                "section_name": normalize_line(section_name),
                "page": int(page),
                "reasons": reasons,
                "score": len(reasons),
            }
        )
    candidates.sort(key=lambda item: (-item["score"], item["block_index"]))
    return candidates[:limit]


def _suspicious_heading_reasons(title: str, body: str, number: str) -> list[str]:
    reasons: list[str] = []
    if not title:
        return reasons

    word_count = len(title.split())
    if PAGE_NOISE_RE.fullmatch(title):
        reasons.append("generic_page_word")
    if MONTH_YEAR_RE.fullmatch(title):
        reasons.append("month_year_only")
    if PURE_NUMBER_RE.fullmatch(title):
        reasons.append("number_only")
    if ICS_RE.fullmatch(title):
        reasons.append("ics_code")
    if DIMENSION_CODE_RE.fullmatch(title):
        reasons.append("dimension_code")
    if COPYRIGHT_RE.search(title):
        reasons.append("copyright_notice")
    if NOISE_MARKER_RE.match(title):
        reasons.append("metadata_marker")
    if title.endswith(("-", "/")):
        reasons.append("trailing_hyphen")
    if LEADING_CONJUNCTION_RE.match(title):
        reasons.append("leading_conjunction")
    if SPLIT_TOKEN_RE.fullmatch(title):
        reasons.append("split_token_line")
    if UNIT_FRAGMENT_RE.fullmatch(title):
        reasons.append("unit_only")
    if SHORT_TOKEN_RE.fullmatch(title):
        reasons.append("short_token")
    if LETTER_RANGE_RE.fullmatch(title):
        reasons.append("letter_range")
    if VALUE_FRAGMENT_RE.fullmatch(title):
        reasons.append("value_fragment")
    if SENTENCE_VERB_RE.search(title) and word_count >= 3:
        reasons.append("sentence_verb_fragment")
    if title.endswith(".") and word_count <= 6:
        reasons.append("sentence_fragment")
    if TRAILING_FRAGMENT_RE.match(title) and word_count <= 5 and len(body) < 160:
        reasons.append("lowercase_fragment")
    if word_count <= 2 and len(title) <= 6 and len(body) < 80 and not str(number).startswith("U"):
        reasons.append("too_short_for_heading")
    return reasons


def _suspicious_fragment_reasons(block_type: str, title: str, content: str) -> list[str]:
    text = normalize_line(title or content)
    if not text:
        return []

    reasons: list[str] = []
    if PAGE_NOISE_RE.fullmatch(text):
        reasons.append("generic_page_word")
    if MONTH_YEAR_RE.fullmatch(text):
        reasons.append("month_year_only")
    if PURE_NUMBER_RE.fullmatch(text):
        reasons.append("number_fragment")
    if ICS_RE.fullmatch(text):
        reasons.append("ics_code")
    if COPYRIGHT_RE.search(text):
        reasons.append("copyright_notice")
    if NOISE_MARKER_RE.match(text):
        reasons.append("metadata_marker")
    if text.endswith(("-", "/")):
        reasons.append("trailing_hyphen")
    if LEADING_CONJUNCTION_RE.match(text):
        reasons.append("leading_conjunction")
    if UNIT_FRAGMENT_RE.fullmatch(text):
        reasons.append("unit_only")
    if SHORT_TOKEN_RE.fullmatch(text):
        reasons.append("short_token")
    if LETTER_RANGE_RE.fullmatch(text):
        reasons.append("letter_range")
    if VALUE_FRAGMENT_RE.fullmatch(text):
        reasons.append("value_fragment")
    if SENTENCE_VERB_RE.search(text) and len(text.split()) >= 3:
        reasons.append("sentence_verb_fragment")
    if MATRIX_FRAGMENT_RE.fullmatch(text):
        reasons.append("matrix_token")
    if DIMENSION_CODE_RE.fullmatch(text):
        reasons.append("dimension_code")
    if REPEATED_NUMBER_FRAGMENT_RE.fullmatch(text):
        reasons.append("number_matrix")
    if len(text) <= 3 and block_type in {TABLE_FRAGMENT_BLOCK, TITLE_BLOCK}:
        reasons.append("very_short_fragment")
    if title and title.endswith(".") and len(title.split()) <= 6:
        reasons.append("sentence_fragment")
    if title and TRAILING_FRAGMENT_RE.match(title) and len(content) < 160:
        reasons.append("lowercase_fragment")
    return reasons


def _request_refinement(
    document: DocumentData,
    section_candidates: list[dict[str, Any]],
    block_candidates: list[dict[str, Any]],
    config: AppConfig,
) -> tuple[dict[str, Any], str]:
    payload = {
        "metadata": metadata_dict(document.metadata),
        "profile": document.profile.to_dict() if document.profile else {},
        "candidate_sections": [
            {
                "candidate_id": item["candidate_id"],
                "section_number": item["section_number"],
                "section_title": item["section_title"],
                "body_excerpt": item["body_excerpt"],
                "body_line_count": item["body_line_count"],
                "previous_section": item["previous_section"],
                "next_section": item["next_section"],
                "local_reasons": item["reasons"],
            }
            for item in section_candidates
        ],
        "candidate_blocks": [
            {
                "candidate_id": item["candidate_id"],
                "block_type": item["block_type"],
                "title": item["title"],
                "content_excerpt": item["content_excerpt"],
                "section_name": item["section_name"],
                "page": item["page"],
                "local_reasons": item["reasons"],
            }
            for item in block_candidates
        ],
    }
    schema = {
        "type": "object",
        "properties": {
            "section_decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "string"},
                        "action": {
                            "type": "string",
                            "enum": [
                                "keep",
                                "rename_heading",
                                "drop_heading_merge_into_previous",
                                "drop_heading_merge_into_next",
                            ],
                        },
                        "new_title": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["candidate_id", "action", "new_title", "reason", "confidence"],
                    "additionalProperties": False,
                },
            },
            "block_decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "string"},
                        "action": {"type": "string", "enum": ["keep", "drop_block", "block_to_body"]},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["candidate_id", "action", "reason", "confidence"],
                    "additionalProperties": False,
                },
            },
            "global_notes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["section_decisions", "block_decisions", "global_notes"],
        "additionalProperties": False,
    }
    return request_structured_json(
        model=config.openai_model,
        system_prompt=(
            "You review locally parsed structures from technical PDFs. "
            "Decide whether suspicious headings are real section headings, should be renamed, or should be merged away. "
            "Also review suspicious blocks such as weak headings and table fragments. "
            "Be conservative: keep content unless it is clearly a date, code line, copyright/page marker, unit-only fragment, "
            "or table-matrix residue that should not remain as standalone structure. Do not invent new technical content."
        ),
        user_payload=payload,
        schema_name="structure_refinement",
        schema=schema,
        timeout=25.0,
    )


def _apply_refinement(
    document: DocumentData,
    section_candidates: list[dict[str, Any]],
    block_candidates: list[dict[str, Any]],
    response: dict[str, Any],
) -> tuple[bool, int]:
    changed = False
    action_count = 0

    section_by_id = {item["candidate_id"]: item for item in section_candidates}
    block_by_id = {item["candidate_id"]: item for item in block_candidates}

    rename_decisions = [item for item in response.get("section_decisions", []) if item.get("action") == "rename_heading"]
    merge_decisions = [item for item in response.get("section_decisions", []) if str(item.get("action", "")).startswith("drop_heading_merge_")]
    block_decisions = [item for item in response.get("block_decisions", []) if item.get("action") in {"drop_block", "block_to_body"}]

    for item in rename_decisions:
        candidate = section_by_id.get(item.get("candidate_id", ""))
        if candidate is None:
            continue
        section = document.sections[candidate["section_index"]]
        old_ref = section_ref(section)
        new_title = normalize_line(item.get("new_title", ""))
        if not new_title or new_title == normalize_line(candidate["section_title"]):
            continue
        _set_field(section, 1, new_title)
        new_ref = section_ref(section)
        _replace_section_refs(document, old_ref, new_ref)
        changed = True
        action_count += 1

    merge_decisions.sort(key=lambda item: section_by_id.get(item.get("candidate_id", ""), {}).get("section_index", -1), reverse=True)
    for item in merge_decisions:
        candidate = section_by_id.get(item.get("candidate_id", ""))
        if candidate is None:
            continue
        section_index = candidate["section_index"]
        if section_index >= len(document.sections):
            continue
        direction = "previous" if item.get("action") == "drop_heading_merge_into_previous" else "next"
        if _merge_section(document, section_index, direction):
            changed = True
            action_count += 1

    block_actions = []
    for item in block_decisions:
        candidate = block_by_id.get(item.get("candidate_id", ""))
        if candidate is None:
            continue
        block_actions.append((candidate["block_index"], item.get("action")))

    for block_index, action in sorted(block_actions, key=lambda pair: pair[0], reverse=True):
        if not (0 <= block_index < len(document.blocks)):
            continue
        if action == "drop_block":
            del document.blocks[block_index]
            changed = True
            action_count += 1
        elif action == "block_to_body":
            block = document.blocks[block_index]
            title = normalize_line(_get_field(block, 1))
            content = normalize_line(_get_field(block, 2))
            merged = "\n".join([line for line in [title, content] if line])
            _set_field(block, 0, BODY_BLOCK)
            _set_field(block, 1, "")
            _set_field(block, 2, merged)
            changed = True
            action_count += 1

    return changed, action_count


def _merge_section(document: DocumentData, section_index: int, direction: str) -> bool:
    if not document.sections or section_index >= len(document.sections):
        return False
    if direction == "previous" and section_index == 0:
        direction = "next"
    if direction == "next" and section_index >= len(document.sections) - 1:
        direction = "previous"
    if direction == "previous" and section_index == 0:
        return False
    if direction == "next" and section_index >= len(document.sections) - 1:
        return False

    source = document.sections[section_index]
    target_index = section_index - 1 if direction == "previous" else section_index + 1
    target = document.sections[target_index]

    source_ref = section_ref(source)
    target_ref = section_ref(target)
    source_title = normalize_line(_get_field(source, 1))
    source_body = normalize_line(_get_field(source, 4))

    merged_lines: list[str] = []
    if _preserve_title_as_body(source_title):
        merged_lines.append(source_title)
    if source_body:
        merged_lines.extend([line for line in source_body.splitlines() if normalize_line(line)])
    if merged_lines:
        target_body = str(_get_field(target, 4))
        combined = _merge_body_text(target_body, "\n".join(merged_lines), prepend=direction == "next")
        _set_field(target, 4, combined)

    _replace_section_refs(document, source_ref, target_ref)
    del document.sections[section_index]
    return True


def _merge_body_text(existing: str, extra: str, prepend: bool = False) -> str:
    existing_lines = [normalize_line(line) for line in str(existing).splitlines() if normalize_line(line)]
    extra_lines = [normalize_line(line) for line in str(extra).splitlines() if normalize_line(line)]
    combined = extra_lines + existing_lines if prepend else existing_lines + extra_lines
    deduped: list[str] = []
    seen: set[str] = set()
    for line in combined:
        if line and line not in seen:
            seen.add(line)
            deduped.append(line)
    return "\n".join(deduped)


def _preserve_title_as_body(title: str) -> bool:
    title = normalize_line(title)
    if not title:
        return False
    if any(pattern.fullmatch(title) for pattern in (PAGE_NOISE_RE, MONTH_YEAR_RE, PURE_NUMBER_RE, ICS_RE, DIMENSION_CODE_RE, SPLIT_TOKEN_RE, UNIT_FRAGMENT_RE)):
        return False
    if COPYRIGHT_RE.search(title):
        return False
    return True


def _replace_section_refs(document: DocumentData, old_ref: str, new_ref: str) -> None:
    old_ref = normalize_line(old_ref)
    new_ref = normalize_line(new_ref)
    if not old_ref or not new_ref or old_ref == new_ref:
        return

    for record in document.tables:
        _replace_field_if_equal(record, 2, old_ref, new_ref)
    for record in document.numeric_parameters:
        _replace_field_if_equal(record, 7, old_ref, new_ref)
    for record in document.rules:
        _replace_field_if_equal(record, 3, old_ref, new_ref)
    for record in document.inspections:
        _replace_field_if_equal(record, 4, old_ref, new_ref)
    for record in document.standards:
        _replace_field_if_equal(record, 3, old_ref, new_ref)
    for record in document.blocks:
        _replace_field_if_equal(record, 4, old_ref, new_ref)


def _replace_field_if_equal(record: Any, index: int, old_value: str, new_value: str) -> None:
    current = normalize_line(str(_get_field(record, index)))
    if current == old_value:
        _set_field(record, index, new_value)


def _reset_views(document: DocumentData) -> None:
    document.nodes_v2 = []
    document.parameter_facts_v2 = []
    document.rule_facts_v2 = []
    document.standard_facts_v2 = []
    document.parsed_view = None


def _hard_heading_reasons() -> set[str]:
    return {
        "generic_page_word",
        "month_year_only",
        "number_only",
        "ics_code",
        "dimension_code",
        "copyright_notice",
        "metadata_marker",
        "trailing_hyphen",
        "leading_conjunction",
        "split_token_line",
        "unit_only",
        "short_token",
        "letter_range",
        "value_fragment",
        "sentence_verb_fragment",
    }


def _hard_block_reasons() -> set[str]:
    return {
        "generic_page_word",
        "month_year_only",
        "number_fragment",
        "ics_code",
        "copyright_notice",
        "metadata_marker",
        "trailing_hyphen",
        "leading_conjunction",
        "unit_only",
        "short_token",
        "letter_range",
        "value_fragment",
        "sentence_verb_fragment",
        "matrix_token",
        "number_matrix",
        "dimension_code",
        "very_short_fragment",
    }


def _get_field(record: Any, index: int) -> Any:
    return getattr(record, fields(record)[index].name)


def _set_field(record: Any, index: int, value: Any) -> None:
    setattr(record, fields(record)[index].name, value)
