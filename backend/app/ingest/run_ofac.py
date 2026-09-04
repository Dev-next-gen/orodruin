"""CLI for the OFAC sanctions ingester.

    python -m app.ingest.run_ofac
"""

from app.db import Base, engine
from app.ingest.ofac import ingest_ofac

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print(ingest_ofac())
