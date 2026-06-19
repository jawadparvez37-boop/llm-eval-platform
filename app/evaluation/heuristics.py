import math
import re
from collections import Counter


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}


def lexical_overlap(left: str, right: str) -> float:
    a = _tokenize(left)
    b = _tokenize(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def context_precision(answer: str, context: str) -> float:
    answer_tokens = _tokenize(answer)
    context_tokens = _tokenize(context)
    if not answer_tokens:
        return 0.0
    grounded = len(answer_tokens & context_tokens)
    return grounded / len(answer_tokens)


def answer_relevance(answer: str, expected: str) -> float:
    return lexical_overlap(answer, expected)


def faithfulness_heuristic(answer: str, context: str) -> float:
    overlap = context_precision(answer, context)
    unsupported = _unsupported_claim_penalty(answer, context)
    return max(0.0, min(1.0, overlap - unsupported))


def _unsupported_claim_penalty(answer: str, context: str) -> float:
    answer_nums = set(re.findall(r"\b\d+\b", answer))
    context_nums = set(re.findall(r"\b\d+\b", context))
    extra = answer_nums - context_nums
    if not extra:
        return 0.0
    return min(0.35, 0.1 * len(extra))


def cosine_similarity_counts(left: str, right: str) -> float:
    a = Counter(_tokenize(left))
    b = Counter(_tokenize(right))
    if not a or not b:
        return 0.0
    dot = sum(a[token] * b.get(token, 0) for token in a)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def passes_threshold(faithfulness: float, relevance: float, precision: float) -> bool:
    return faithfulness >= 0.55 and relevance >= 0.45 and precision >= 0.50
