"""CLI for the GDACS ingester.

    python -m app.ingest.run_gdacs --once
    python -m app.ingest.run_gdacs --loop 3600
"""

import argparse
import time

from app.db import Base, engine
from app.ingest.gdacs import ingest_gdacs


def main():
    ap = argparse.ArgumentParser(description="GDACS ingester")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", type=int, default=0)
    ap.parse_args()
    args = ap.parse_args()
    Base.metadata.create_all(engine)
    if args.loop:
        while True:
            try:
                print(ingest_gdacs(), flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"gdacs error: {exc}", flush=True)
            time.sleep(args.loop)
    else:
        print(ingest_gdacs())


if __name__ == "__main__":
    main()
