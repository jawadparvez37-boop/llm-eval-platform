from openai import OpenAI

from app.config import settings

_DOCS = {
    "refund": "Refunds are available within 30 days for unused products. Contact support with your order ID.",
    "shipping": "Standard shipping takes 3-5 business days. Express options are available at checkout.",
    "support": "Support hours are Monday to Friday, 9am-6pm Central Time.",
    "billing": "Invoices are generated on the first business day of each month for enterprise accounts.",
    "security": "API keys must be rotated every 90 days. MFA is required for admin accounts.",
}


def _select_context(question: str) -> str:
    q = question.lower()
    chunks = []
    for key, text in _DOCS.items():
        if key in q or any(token in q for token in key.split()):
            chunks.append(text)
    if not chunks:
        chunks = list(_DOCS.values())
    return "\n".join(chunks[:3])


def generate_answer(question: str, override_context: str | None = None) -> str:
    context = override_context or _select_context(question)

    if not settings.openai_api_key:
        return _fallback_answer(question, context)

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.chat_model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "Answer using only the provided context. If unknown, say you do not have enough information.",
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content or ""


def _fallback_answer(question: str, context: str) -> str:
    for line in context.split("\n"):
        if any(token in line.lower() for token in question.lower().split()[:3]):
            return line
    return context.split("\n")[0]
