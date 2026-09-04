"""CLI for the OpenSanctions ingester.

    python -m app.ingest.run_opensanctions
"""

from app.db import Base, engine
from app.ingest.opensanctions import ingest_opensanctions

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    print(ingest_opensanctions())
