from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import asdict
import json
from pathlib import Path

from sqlalchemy.orm import Session

from evermind.db.session import SessionLocal
from evermind.org.seed_schema import load_org_seed
from evermind.org.seed_service import SeedSummary, seed_org


def run_seed(path: Path, session: Session) -> SeedSummary:
    return seed_org(session, load_org_seed(path))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed EverMind org data")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    with SessionLocal.begin() as session:
        summary = run_seed(args.path, session)
    print(json.dumps(asdict(summary), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
