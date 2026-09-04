"""CLI for the ACLED ingester.

    python -m app.ingest.run_acled --pages 4 --limit 500
"""

import argparse

from app.db import Base, engine
from app.ingest.acled import ingest_acled


def main():
    ap = argparse.ArgumentParser(description="ACLED ingester")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    Base.metadata.create_all(engine)
    print(ingest_acled(pages=args.pages, limit=args.limit))


if __name__ == "__main__":
    main()
