"""Run the AISStream vessel collector forever.

    python -m app.ingest.run_vessels
"""

import asyncio

from app.db import Base, engine
from app.ingest.aisstream import run_forever

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    asyncio.run(run_forever())
