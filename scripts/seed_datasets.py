import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.datasets.manager import seed_from_files


def main() -> None:
    ids = seed_from_files()
    print(f"seeded {len(ids)} datasets")


if __name__ == "__main__":
    main()
