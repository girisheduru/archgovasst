"""Rank passages from one uploaded design for every applicable rule."""

import math
import re
from collections import Counter
from operator import mul

from ..providers.openai import embed_texts

PASSAGE_CHARS = 2_000
OVERLAP_CHARS = 300
PASSAGES_PER_RULE = 3


def build_passages(sections: dict[str, str]) -> list[dict[str, str]]:
    """Group adjacent short sections and split long ones, preserving citation labels."""
    passages = []
    pending = {}
    size = 0
    for source, text in sections.items():
        length = len(text) + len(source) + 2
        if pending and size + length > PASSAGE_CHARS:
            passages.append(pending)
            pending = {}
            size = 0
        if len(text) <= PASSAGE_CHARS:
            pending[source] = text
            size += length
            continue
        start = 0
        while start < len(text):
            end = start + PASSAGE_CHARS
            passages.append({source: text[start:end].strip()})
            if end >= len(text):
                break
            start = end - OVERLAP_CHARS
    if pending:
        passages.append(pending)
    return passages


def _terms(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.casefold()))


def _unit_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def rank_passages(rules: list[dict], passages: list[dict[str, str]]) -> dict[str, list[int]]:
    texts = ["\n".join(sections.values()) for sections in passages]
    queries = [f"{rule['quote']}\n{rule['evidence_required']}" for rule in rules]
    vectors = embed_texts(texts + queries, timeout=30, max_retries=0)
    if len(vectors) != len(texts) + len(queries):
        raise ValueError("Incomplete passage embeddings.")
    passage_vectors = [_unit_vector(vector) for vector in vectors[:len(texts)]]
    query_vectors = [_unit_vector(vector) for vector in vectors[len(texts):]]

    terms = [_terms(text) for text in texts]
    frequency = Counter(term for passage_terms in terms for term in passage_terms)
    weights = {term: math.log((1 + len(terms)) / (1 + count)) for term, count in frequency.items()}
    ranked = {}
    for rule, query, vector in zip(rules, queries, query_vectors, strict=True):
        query_terms = _terms(query)
        keyword_scores = [sum(weights[term] for term in sorted(query_terms & item)) for item in terms]
        semantic_scores = [sum(map(mul, vector, passage)) for passage in passage_vectors]
        combined = Counter()
        for scores in (keyword_scores, semantic_scores):
            order = sorted(range(len(scores)), key=scores.__getitem__, reverse=True)
            for rank, index in enumerate(order, 1):
                if scores[index] > 0:
                    combined[index] += 1 / (60 + rank)
        ranked[rule["id"]] = [index for index, _ in combined.most_common(PASSAGES_PER_RULE)]
    return ranked
