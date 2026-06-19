import json

from openai import OpenAI

from app.config import settings


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for LLM judge")
    return OpenAI(api_key=settings.openai_api_key)


def judge_scores(question: str, answer: str, context: str, expected: str) -> dict[str, float]:
    schema = {
        "type": "object",
        "properties": {
            "faithfulness": {"type": "number"},
            "answer_relevance": {"type": "number"},
            "context_precision": {"type": "number"},
        },
        "required": ["faithfulness", "answer_relevance", "context_precision"],
        "additionalProperties": False,
    }

    prompt = (
        "Score the model answer from 0 to 1.\n"
        "faithfulness: answer stays grounded in context\n"
        "answer_relevance: answer addresses the question and aligns with expected answer\n"
        "context_precision: answer uses relevant context facts\n\n"
        f"Question: {question}\n"
        f"Context: {context}\n"
        f"Expected: {expected}\n"
        f"Answer: {answer}\n"
    )

    response = _client().chat.completions.create(
        model=settings.judge_model,
        messages=[
            {"role": "system", "content": "Return JSON only with scores between 0 and 1."},
            {"role": "user", "content": prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "eval_scores", "schema": schema},
        },
        temperature=0,
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    return {
        "faithfulness": float(data.get("faithfulness", 0)),
        "answer_relevance": float(data.get("answer_relevance", 0)),
        "context_precision": float(data.get("context_precision", 0)),
    }
