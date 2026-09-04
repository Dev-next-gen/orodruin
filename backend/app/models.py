from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Actor(Base):
    """Ontology object: Actor (state, non-state, individual, organization)."""

    __tablename__ = "actors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    type_code: Mapped[str | None] = mapped_column(String(16), nullable=True)


class Event(Base):
    """Ontology object: Event (conflict, cooperation, statement, movement).

    Maps directly from a GDELT 2.0 export row.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # GLOBALEVENTID
    sqldate: Mapped[int] = mapped_column(Integer, index=True)
    date_added: Mapped[datetime] = mapped_column(DateTime, index=True)
    event_code: Mapped[str | None] = mapped_column(String(8))
    event_root_code: Mapped[str | None] = mapped_column(String(8), index=True)
    quad_class: Mapped[int | None] = mapped_column(Integer, index=True)
    goldstein: Mapped[float | None] = mapped_column(Float)
    avg_tone: Mapped[float | None] = mapped_column(Float)
    num_mentions: Mapped[int | None] = mapped_column(Integer)
    num_sources: Mapped[int | None] = mapped_column(Integer)
    num_articles: Mapped[int | None] = mapped_column(Integer)
    actor1_id: Mapped[int | None] = mapped_column(ForeignKey("actors.id"), nullable=True)
    actor2_id: Mapped[int | None] = mapped_column(ForeignKey("actors.id"), nullable=True)
    geo_fullname: Mapped[str | None] = mapped_column(String(255))
    geo_country: Mapped[str | None] = mapped_column(String(8), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    source_url: Mapped[str | None] = mapped_column(String(1024))

    actor1 = relationship("Actor", foreign_keys=[actor1_id], lazy="joined")
    actor2 = relationship("Actor", foreign_keys=[actor2_id], lazy="joined")


Index("ix_events_geo", Event.lat, Event.lon)


class Fire(Base):
    """Ontology object: Hazard/Fire — active fire detection (NASA FIRMS, global)."""

    __tablename__ = "fires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ext_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    lat: Mapped[float] = mapped_column(Float, index=True)
    lon: Mapped[float] = mapped_column(Float, index=True)
    brightness: Mapped[float | None] = mapped_column(Float)
    frp: Mapped[float | None] = mapped_column(Float)  # fire radiative power (MW)
    confidence: Mapped[str | None] = mapped_column(String(16))
    acq_datetime: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    satellite: Mapped[str | None] = mapped_column(String(32))
    daynight: Mapped[str | None] = mapped_column(String(4))
    source: Mapped[str | None] = mapped_column(String(48), index=True)
    country: Mapped[str | None] = mapped_column(String(8), index=True)


class Conflict(Base):
    """Ontology object: Event (armed conflict) — ACLED record."""

    __tablename__ = "conflicts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # ACLED data_id
    event_date: Mapped[str | None] = mapped_column(String(16), index=True)
    event_type: Mapped[str | None] = mapped_column(String(64), index=True)
    sub_event_type: Mapped[str | None] = mapped_column(String(96))
    actor1: Mapped[str | None] = mapped_column(String(255))
    actor2: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(64), index=True)
    admin1: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    fatalities: Mapped[int | None] = mapped_column(Integer, index=True)
    notes: Mapped[str | None] = mapped_column(String(2000))
    src: Mapped[str | None] = mapped_column(String(255))


class Vessel(Base):
    """Ontology object: Asset (vessel) — latest AIS position (AISStream)."""

    __tablename__ = "vessels"

    mmsi: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(128))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    sog: Mapped[float | None] = mapped_column(Float)  # speed over ground (knots)
    cog: Mapped[float | None] = mapped_column(Float)  # course over ground (deg)
    heading: Mapped[int | None] = mapped_column(Integer)
    ship_type: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Disaster(Base):
    """Ontology object: Hazard — GDACS disaster alert (scored green/orange/red)."""

    __tablename__ = "disasters"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    event_type: Mapped[str | None] = mapped_column(String(8), index=True)  # EQ/TC/FL/VO/DR/WF
    alert_level: Mapped[str | None] = mapped_column(String(16), index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(128), index=True)
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    from_date: Mapped[str | None] = mapped_column(String(32))
    severity: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Sanction(Base):
    """Ontology object: Actor/Org — OFAC SDN sanctioned entity (US Treasury)."""

    __tablename__ = "sanctions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # ent_num
    name: Mapped[str] = mapped_column(String(512), index=True)
    sdn_type: Mapped[str | None] = mapped_column(String(48))  # individual/entity/vessel/aircraft
    program: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    remarks: Mapped[str | None] = mapped_column(String(2000))


class GlobalSanction(Base):
    """OpenSanctions consolidated entity (EU/UN/UK/US/... sanctions & watchlists)."""

    __tablename__ = "os_entities"

    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    name: Mapped[str] = mapped_column(String(512), index=True)
    schema: Mapped[str | None] = mapped_column(String(48))  # Person/Organization/Vessel...
    aliases: Mapped[str | None] = mapped_column(String(1500))
    countries: Mapped[str | None] = mapped_column(String(255))
    programs: Mapped[str | None] = mapped_column(String(1024))
    datasets: Mapped[str | None] = mapped_column(String(512))
