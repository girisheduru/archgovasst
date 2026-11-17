"""Extract rule versions from Word documents using the standards template."""

import re
from datetime import date
from pathlib import Path

from ..agent.documents import parse_document
from .models import Rule

RULE_HEADING = re.compile(r"([A-Z][A-Z0-9]*-\d+) .+")
EVIDENCE_PREFIX = "Evidence expected in the design document:"


def extract_rules(filename: str, payload: bytes) -> list[Rule]:
    if Path(filename).suffix.lower() != ".docx":
        raise ValueError(f"{filename}: use a Word (.docx) standards document.")
    try:
        blocks = parse_document(filename, payload)
    except Exception as exc:
        raise ValueError(f"{filename}: could not read the Word document.") from exc

    ordered_blocks = list(blocks.items())
    paragraphs = [text if label.startswith("Paragraph ") else "" for label, text in ordered_blocks]
    try:
        start = paragraphs.index("3. Rules")
        end = paragraphs.index("4. Exceptions", start + 1)
    except ValueError as exc:
        raise ValueError(f"{filename}: expected '3. Rules' followed by '4. Exceptions'.") from exc

    metadata = " ".join(text for label, text in ordered_blocks[:start] if label.startswith("Table "))
    standards = re.findall(r"\bDocument ID \| (STD-\d+)(?= |$)", metadata)
    dates = re.findall(r"\bEffective date \| (\d{4}-\d{2}-\d{2})(?= |$)", metadata)
    if len(standards) != 1 or len(dates) != 1:
        raise ValueError(f"{filename}: expected one Document ID and one ISO Effective date in the metadata table.")
    try:
        effective_date = date.fromisoformat(dates[0])
    except ValueError as exc:
        raise ValueError(f"{filename}: invalid Effective date {dates[0]}.") from exc

    entries = paragraphs[start + 1:end]
    if not entries or len(entries) % 3 or "" in entries:
        raise ValueError(f"{filename}: each rule needs a heading, statement and evidence paragraph.")
    rules = []
    for index in range(0, len(entries), 3):
        heading, quote, evidence = entries[index:index + 3]
        match = RULE_HEADING.fullmatch(heading)
        if (
            not match
            or RULE_HEADING.fullmatch(quote)
            or quote.startswith(EVIDENCE_PREFIX)
            or not evidence.startswith(EVIDENCE_PREFIX + " ")
        ):
            raise ValueError(f"{filename}: invalid rule block starting at '{heading}'.")
        rules.append(Rule(
            id=match[1],
            standard=standards[0],
            effective_date=effective_date,
            quote=quote,
            evidence_required=evidence,
            gap_risk="medium",
            document_types=["solution_design", "architecture_decision"],
        ))
    return rules
