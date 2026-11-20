"""Load the bundled design benchmark and its matching policy snapshot."""

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from ..agent.documents import parse_document
from ..agent.policy import RISK_TIERS
from ..standards_store.models import RiskTier
from ..standards_store.source_documents import extract_rules
from .metrics import AnswerKey

DATADOCS = Path(__file__).resolve().parents[2] / "datadocs"
DECLARED_TIERS: dict[str, RiskTier] = {"Tier 1": "high", "Tier 2": "medium", "Tier 3": "low"}
FINDING_TYPES = {"PLANTED GAP", "MISSING SECTION", "NOT EVIDENCED"}


@dataclass(frozen=True)
class DesignCase:
    doc_id: str
    sections: dict[str, str]
    source_digest: str
    declared_tier: RiskTier
    suggested_outcome: str
    key: AnswerKey


def _rows(workbook, sheet_name, columns):
    rows = workbook[sheet_name].values
    header = next(rows, ())
    if not set(columns).issubset(header):
        raise ValueError(f"Answer key sheet {sheet_name!r} requires columns {', '.join(columns)}.")
    indices = [header.index(column) for column in columns]
    for row in rows:
        if any(value is not None for value in row):
            yield tuple(row[index] for index in indices)


def load_dataset(root: Path = DATADOCS):
    from openpyxl import load_workbook

    rules = {}
    for path in sorted((root / "standards").glob("STD-*.docx")):
        for rule in extract_rules(path.name, path.read_bytes()):
            if rule.id in rules:
                raise ValueError(f"Duplicate benchmark standard rule {rule.id}.")
            rules[rule.id] = rule

    workbook = load_workbook(root / "Answer_Key.xlsx", read_only=True, data_only=True)
    try:
        labeled_rules = dict(_rows(workbook, "Rules", ("Rule ID", "Rule")))
        if not rules or labeled_rules != {rule.id: rule.quote for rule in rules.values()}:
            raise ValueError("The workbook's Rules sheet must match the bundled Word standards.")
        summary = list(_rows(
            workbook, "Summary", ("Doc ID", "File", "Tier", "Expected findings", "Suggested outcome")
        ))
        findings = list(_rows(workbook, "Expected findings", ("Doc ID", "Rule ID", "Finding type")))
    finally:
        workbook.close()

    doc_ids = {doc_id for doc_id, *_ in summary}
    if not summary or None in doc_ids or len(doc_ids) != len(summary):
        raise ValueError("The workbook must have one Summary row per design ID.")
    gaps = defaultdict(set)
    for doc_id, rule_id, finding_type in findings:
        if (
            doc_id not in doc_ids or rule_id not in rules or finding_type not in FINDING_TYPES
            or rule_id in gaps[doc_id]
        ):
            raise ValueError(f"Invalid or duplicate expected finding for {doc_id}, {rule_id}.")
        gaps[doc_id].add(rule_id)

    cases = {}
    for doc_id, filename, tier, expected_count, outcome in summary:
        if not isinstance(filename, str) or Path(filename).name != filename or Path(filename).suffix != ".docx":
            raise ValueError(f"{doc_id}: expected a Word filename in the Summary sheet.")
        if tier not in DECLARED_TIERS or expected_count != len(gaps[doc_id]):
            raise ValueError(f"{doc_id}: check the declared tier and expected finding count.")
        path = root / "solution-designs" / filename
        payload = path.read_bytes()
        sections = parse_document(path.name, payload)
        declared_tier = DECLARED_TIERS[tier]
        expected_tier = max(
            [declared_tier, *(rules[rule_id].gap_risk for rule_id in gaps[doc_id])],
            key=RISK_TIERS.index,
        )
        cases[doc_id] = DesignCase(
            doc_id, sections, sha256(payload).hexdigest(), declared_tier, outcome,
            AnswerKey(not_evidenced_rule_ids=gaps[doc_id], risk_tier=expected_tier),
        )
    return cases, [rule.model_dump(mode="json") for rule in sorted(rules.values(), key=lambda rule: rule.id)]
