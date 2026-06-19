from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import db
from app.datasets.manager import seed_from_files
from app.evaluation.engine import run_evaluation
from app.models import (
    DatasetCreate,
    DatasetSummary,
    EvaluationRequest,
    EvaluationRun,
    MetricsSummary,
    TraceCreate,
    TraceRecord,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    seed_from_files()
    db.purge_old_traces()
    yield


app = FastAPI(title="LLM Evaluation Platform", lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent / "static"
DOCS_DIR = Path(__file__).resolve().parents[1] / "docs"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/docs", StaticFiles(directory=DOCS_DIR), name="docs")


@app.get("/")
def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/traces", response_model=TraceRecord)
def create_trace(payload: TraceCreate):
    return db.insert_trace(payload)


@app.get("/traces", response_model=list[TraceRecord])
def get_traces(service: str | None = None, limit: int = Query(default=50, ge=1, le=200)):
    return db.list_traces(service, limit)


@app.post("/datasets", response_model=DatasetSummary)
def create_dataset(payload: DatasetCreate):
    try:
        return db.create_dataset(payload)
    except Exception as exc:
        raise HTTPException(status_code=409, detail="dataset name already exists") from exc


@app.get("/datasets", response_model=list[DatasetSummary])
def list_datasets():
    return db.list_datasets()


@app.get("/datasets/{dataset_id}", response_model=DatasetSummary)
def get_dataset(dataset_id: str):
    row = db.get_dataset(dataset_id)
    if not row:
        raise HTTPException(status_code=404, detail="dataset not found")
    summary, _ = row
    return summary


@app.post("/evaluations/run", response_model=EvaluationRun)
def start_evaluation(request: EvaluationRequest):
    try:
        return run_evaluation(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/evaluations", response_model=list[EvaluationRun])
def list_evaluations(dataset_id: str | None = None):
    return db.list_evaluation_runs(dataset_id)


@app.get("/evaluations/{run_id}", response_model=EvaluationRun)
def get_evaluation(run_id: str):
    run = db.get_evaluation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return run


@app.get("/evaluations/{run_id}/summary", response_model=MetricsSummary)
def evaluation_summary(run_id: str):
    run = db.get_evaluation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="evaluation run not found")
    return db.build_metrics_summary(run.results)


@app.get("/metrics/overview")
def metrics_overview():
    runs = db.list_evaluation_runs()[:10]
    traces = db.list_traces(None, 100)
    if not traces:
        avg_latency = 0
    else:
        avg_latency = round(sum(t.latency_ms for t in traces) / len(traces), 2)

    return {
        "evaluation_runs": len(runs),
        "trace_count": len(traces),
        "avg_trace_latency_ms": avg_latency,
        "latest_runs": [
            {
                "id": run.id,
                "name": run.run_name,
                "pass_rate": run.summary.get("pass_rate", 0),
                "status": run.status,
            }
            for run in runs
        ],
    }
