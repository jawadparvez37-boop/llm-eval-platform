import json
from pathlib import Path

from app import db
from app.models import DatasetCreate, GoldenItem

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_DIR = ROOT / "data" / "golden"


def load_json_dataset(path: Path) -> DatasetCreate:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = [GoldenItem(**row) for row in payload["items"]]
    return DatasetCreate(
        name=payload["name"],
        description=payload.get("description", ""),
        items=items,
    )


def seed_from_files() -> list[str]:
    db.init_db()
    created: list[str] = []
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        payload = load_json_dataset(path)
        try:
            summary = db.create_dataset(payload)
            created.append(summary.id)
        except Exception:
            existing = next((d for d in db.list_datasets() if d.name == payload.name), None)
            if existing:
                created.append(existing.id)
    return created
