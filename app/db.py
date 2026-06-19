import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.models import (
    DatasetCreate,
    DatasetSummary,
    EvaluationRun,
    GoldenItem,
    MetricsSummary,
    QuestionScore,
    TraceCreate,
    TraceRecord,
    TraceStatus,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    operation TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL,
    status TEXT NOT NULL,
    input_preview TEXT NOT NULL DEFAULT '',
    output_preview TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS traces_created_idx ON traces(created_at);
CREATE INDEX IF NOT EXISTS traces_service_idx ON traces(service);

CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    items TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    run_name TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '{}',
    results TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS evaluation_runs_dataset_idx ON evaluation_runs(dataset_id);
"""


def _db_path() -> Path:
    path = Path(settings.database_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | str) -> datetime:
    if isinstance(dt, datetime):
        return dt
    return datetime.fromisoformat(dt.replace("Z", "+00:00"))


def init_db() -> None:
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()


def insert_trace(payload: TraceCreate) -> TraceRecord:
    trace_id = str(uuid.uuid4())
    now = _now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO traces (
                id, service, operation, model, prompt_tokens, completion_tokens,
                latency_ms, status, input_preview, output_preview, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                payload.service,
                payload.operation,
                payload.model,
                payload.prompt_tokens,
                payload.completion_tokens,
                payload.latency_ms,
                payload.status.value,
                payload.input_preview,
                payload.output_preview,
                json.dumps(payload.metadata),
                now.isoformat(),
            ),
        )
        conn.commit()
    return TraceRecord(id=trace_id, created_at=now, **payload.model_dump())


def list_traces(service: str | None, limit: int) -> list[TraceRecord]:
    query = "SELECT * FROM traces"
    params: list = []
    if service:
        query += " WHERE service = ?"
        params.append(service)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        TraceRecord(
            id=row["id"],
            service=row["service"],
            operation=row["operation"],
            model=row["model"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            latency_ms=row["latency_ms"],
            status=TraceStatus(row["status"]),
            input_preview=row["input_preview"],
            output_preview=row["output_preview"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=_iso(row["created_at"]),
        )
        for row in rows
    ]


def purge_old_traces() -> int:
    cutoff = (_now() - timedelta(days=settings.trace_retention_days)).isoformat()
    with connect() as conn:
        cur = conn.execute("DELETE FROM traces WHERE created_at < ?", (cutoff,))
        conn.commit()
        return cur.rowcount


def create_dataset(payload: DatasetCreate) -> DatasetSummary:
    dataset_id = str(uuid.uuid4())
    now = _now()
    items = [item.model_dump() for item in payload.items]
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO datasets (id, name, description, items, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (dataset_id, payload.name, payload.description, json.dumps(items), now.isoformat()),
        )
        conn.commit()
    return DatasetSummary(
        id=dataset_id,
        name=payload.name,
        description=payload.description,
        item_count=len(payload.items),
        created_at=now,
    )


def get_dataset(dataset_id: str) -> tuple[DatasetSummary, list[GoldenItem]] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not row:
        return None
    items = [GoldenItem(**item) for item in json.loads(row["items"])]
    summary = DatasetSummary(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        item_count=len(items),
        created_at=_iso(row["created_at"]),
    )
    return summary, items


def list_datasets() -> list[DatasetSummary]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, name, description, items, created_at FROM datasets ORDER BY created_at DESC"
        ).fetchall()
    output: list[DatasetSummary] = []
    for row in rows:
        items = json.loads(row["items"])
        output.append(
            DatasetSummary(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                item_count=len(items),
                created_at=_iso(row["created_at"]),
            )
        )
    return output


def save_evaluation_run(run: EvaluationRun) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO evaluation_runs (
                id, dataset_id, run_name, status, summary, results, created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                status = excluded.status,
                summary = excluded.summary,
                results = excluded.results,
                completed_at = excluded.completed_at
            """,
            (
                run.id,
                run.dataset_id,
                run.run_name,
                run.status,
                json.dumps(run.summary),
                json.dumps([r.model_dump() for r in run.results]),
                run.created_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
            ),
        )
        conn.commit()


def get_evaluation_run(run_id: str) -> EvaluationRun | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM evaluation_runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return EvaluationRun(
        id=row["id"],
        dataset_id=row["dataset_id"],
        run_name=row["run_name"],
        status=row["status"],
        summary=json.loads(row["summary"] or "{}"),
        results=[QuestionScore(**item) for item in json.loads(row["results"] or "[]")],
        created_at=_iso(row["created_at"]),
        completed_at=_iso(row["completed_at"]) if row["completed_at"] else None,
    )


def list_evaluation_runs(dataset_id: str | None = None) -> list[EvaluationRun]:
    query = "SELECT id, dataset_id, run_name, status, summary, results, created_at, completed_at FROM evaluation_runs"
    params: list = []
    if dataset_id:
        query += " WHERE dataset_id = ?"
        params.append(dataset_id)
    query += " ORDER BY created_at DESC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    runs: list[EvaluationRun] = []
    for row in rows:
        runs.append(
            EvaluationRun(
                id=row["id"],
                dataset_id=row["dataset_id"],
                run_name=row["run_name"],
                status=row["status"],
                summary=json.loads(row["summary"] or "{}"),
                results=[QuestionScore(**item) for item in json.loads(row["results"] or "[]")],
                created_at=_iso(row["created_at"]),
                completed_at=_iso(row["completed_at"]) if row["completed_at"] else None,
            )
        )
    return runs


def build_metrics_summary(results: list[QuestionScore]) -> MetricsSummary:
    if not results:
        return MetricsSummary(
            total=0,
            passed=0,
            failed=0,
            avg_faithfulness=0.0,
            avg_answer_relevance=0.0,
            avg_context_precision=0.0,
            avg_latency_ms=0.0,
            pass_rate=0.0,
        )

    total = len(results)
    passed = sum(1 for row in results if row.passed)
    return MetricsSummary(
        total=total,
        passed=passed,
        failed=total - passed,
        avg_faithfulness=round(sum(r.faithfulness for r in results) / total, 4),
        avg_answer_relevance=round(sum(r.answer_relevance for r in results) / total, 4),
        avg_context_precision=round(sum(r.context_precision for r in results) / total, 4),
        avg_latency_ms=round(sum(r.latency_ms for r in results) / total, 2),
        pass_rate=round(passed / total, 4),
    )
