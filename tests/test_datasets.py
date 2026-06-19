import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_load_golden_dataset():
    path = ROOT / "data" / "golden" / "product-support-golden-set.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["name"] == "product-support-golden-set"
    assert len(payload["items"]) >= 5
