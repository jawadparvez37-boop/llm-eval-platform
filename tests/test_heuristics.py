from app.evaluation import heuristics


def test_pass_threshold():
    assert heuristics.passes_threshold(0.8, 0.7, 0.6) is True
    assert heuristics.passes_threshold(0.4, 0.7, 0.6) is False


def test_context_precision():
    answer = "Refunds are available within 30 days"
    context = "Refunds are available within 30 days for unused products."
    score = heuristics.context_precision(answer, context)
    assert score > 0.5


def test_lexical_overlap():
    score = heuristics.lexical_overlap("refund within 30 days", "refund available 30 days")
    assert score > 0.2
