"""CLI entrypoint for the GDELT ingester.

Examples:
    python -m app.ingest.run --init         # create tables only
    python -m app.ingest.run --once         # ingest the latest slice once
    python -m app.ingest.run --loop 900     # ingest every 15 minutes forever
"""

import argparse
import time

from app.db import Base, engine
from app.ingest.gdelt import ingest_backfill, ingest_once


def init_db():
    Base.metadata.create_all(engine)


def main():
    ap = argparse.ArgumentParser(description="GDELT ingester")
    ap.add_argument("--init", action="store_true", help="create tables and exit")
    ap.add_argument("--once", action="store_true", help="ingest latest slice once")
    ap.add_argument("--backfill", type=int, default=0, help="backfill the last N hours")
    ap.add_argument("--loop", type=int, default=0, help="seconds between runs")
    args = ap.parse_args()

    init_db()

    if args.init and not (args.once or args.loop or args.backfill):
        print("DB initialized.")
        return

    if args.backfill:
        print(f"Backfilling last {args.backfill}h ({args.backfill * 4} slices)…")
        print(ingest_backfill(args.backfill))
        if not (args.once or args.loop):
            return

    if args.loop:
        print(f"Looping every {args.loop}s. Ctrl-C to stop.")
        while True:
            try:
                print(ingest_once(), flush=True)
            except Exception as exc:  # noqa: BLE001
                print(f"ingest error: {exc}", flush=True)
            time.sleep(args.loop)
    else:
        print(ingest_once())


if __name__ == "__main__":
    main()
