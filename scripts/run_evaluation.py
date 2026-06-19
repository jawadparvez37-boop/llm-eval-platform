import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.datasets.manager import seed_from_files
from app.evaluation.engine import run_evaluation
from app.models import EvaluationRequest


def main() -> None:
    db.init_db()
    dataset_ids = seed_from_files()
    if not dataset_ids:
        print("no datasets found")
        return

    for dataset_id in dataset_ids:
        run = run_evaluation(
            EvaluationRequest(
                dataset_id=dataset_id,
                run_name="cli-baseline-run",
                use_llm_judge=False,
            )
        )
        print(f"run={run.id} dataset={dataset_id} pass_rate={run.summary.get('pass_rate')}")


if __name__ == "__main__":
    main()
