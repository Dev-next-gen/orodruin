"""CLI for the NASA FIRMS fire ingester.

    python -m app.ingest.run_fires --days 1
    python -m app.ingest.run_fires --loop 10800   # every 3h
"""

import argparse
import time

from app.db import Base, engine
from app.ingest.firms import ingest_fires


def main():
    ap = argparse.ArgumentParser(description="NASA FIRMS ingester")
    ap.add_argument("--days", type=int, default=1, help="lookback window (1-10)")
    ap.add_argument("--loop", type=int, default=0, help="seconds between runs")
    args = ap.parse_args()

    Base.metadata.create_all(engine)

    if args.loop:
        print(f"FIRMS loop every {args.loop}s.")
        while True:
            try:
                print(ingest_fires(args.days), flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"firms error: {exc}", flush=True)
            time.sleep(args.loop)
    else:
        print(ingest_fires(args.days))


if __name__ == "__main__":
    main()
