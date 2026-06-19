import time
import uuid
from datetime import datetime, timezone

from app import db
from app.config import settings
from app.evaluation import heuristics
from app.evaluation.llm_judge import judge_scores
from app.models import EvaluationRequest, EvaluationRun, GoldenItem, QuestionScore, TraceCreate, TraceStatus
from app.rag.reference_pipeline import generate_answer


def score_item(item: GoldenItem, use_llm_judge: bool) -> QuestionScore:
    started = time.perf_counter()
    generated = generate_answer(item.question, item.reference_context)
    latency_ms = int((time.perf_counter() - started) * 1000)

    db.insert_trace(
        TraceCreate(
            service="rag-reference",
            operation="generate",
            model=settings.chat_model,
            prompt_tokens=max(1, len(item.question.split())),
            completion_tokens=max(1, len(generated.split())),
            latency_ms=latency_ms,
            status=TraceStatus.success,
            input_preview=item.question[:280],
            output_preview=generated[:280],
            metadata={"dataset_item": item.id},
        )
    )

    if use_llm_judge and settings.openai_api_key and settings.enable_llm_judge:
        try:
            scores = judge_scores(item.question, generated, item.reference_context, item.expected_answer)
        except Exception:
            scores = _heuristic_scores(generated, item)
    else:
        scores = _heuristic_scores(generated, item)

    faithfulness = round(scores["faithfulness"], 4)
    relevance = round(scores["answer_relevance"], 4)
    precision = round(scores["context_precision"], 4)

    return QuestionScore(
        item_id=item.id,
        question=item.question,
        generated_answer=generated,
        faithfulness=faithfulness,
        answer_relevance=relevance,
        context_precision=precision,
        latency_ms=latency_ms,
        passed=heuristics.passes_threshold(faithfulness, relevance, precision),
    )


def _heuristic_scores(answer: str, item: GoldenItem) -> dict[str, float]:
    return {
        "faithfulness": heuristics.faithfulness_heuristic(answer, item.reference_context),
        "answer_relevance": heuristics.answer_relevance(answer, item.expected_answer),
        "context_precision": heuristics.context_precision(answer, item.reference_context),
    }


def run_evaluation(request: EvaluationRequest) -> EvaluationRun:
    dataset = db.get_dataset(request.dataset_id)
    if not dataset:
        raise ValueError("dataset not found")

    summary, items = dataset
    run_id = str(uuid.uuid4())
    created = datetime.now(timezone.utc)
    use_judge = settings.enable_llm_judge if request.use_llm_judge is None else request.use_llm_judge

    run = EvaluationRun(
        id=run_id,
        dataset_id=summary.id,
        run_name=request.run_name,
        status="running",
        created_at=created,
    )
    db.save_evaluation_run(run)

    results: list[QuestionScore] = []
    for item in items:
        results.append(score_item(item, use_judge))

    metrics = db.build_metrics_summary(results)
    run.results = results
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = metrics.model_dump()
    db.save_evaluation_run(run)
    return run
