import hashlib

from src.reviewer import ISSUE_DEDUCTIONS
from src.summarizer import _summary_system_prompt
from src.tagger import _tag_system_prompt


def _short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def prompt_signature() -> str:
    """Return the combined summarizer/tagger system prompt 8-hex signature."""
    joined = _summary_system_prompt() + "\n---\n" + _tag_system_prompt()
    return _short_hash(joined)


def reviewer_signature() -> str:
    """Return the normalized reviewer deduction rules 8-hex signature."""
    canon = "\n".join(
        f"{key}|{value[0]}|{value[1]:.2f}"
        for key, value in sorted(ISSUE_DEDUCTIONS.items())
    )
    return _short_hash(canon)
