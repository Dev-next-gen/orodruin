from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.events import _apply_filters
from app.cameo import root_label
from app.db import get_db
from app.llm import available, chat
from app.models import Disaster, Event

router = APIRouter(prefix="/api", tags=["analysis"])


def _format_events(events) -> str:
    lines = []
    for e in events:
        a1 = e.actor1.name if e.actor1 else "?"
        a2 = e.actor2.name if e.actor2 else "?"
        tone = f"{e.avg_tone:.1f}" if e.avg_tone is not None else "?"
        loc = e.geo_fullname or e.geo_country or "?"
        lines.append(
            f"- [{root_label(e.event_root_code)}] {a1} -> {a2} @ {loc} "
            f"(tone {tone}, {e.num_mentions or 0} mentions)"
        )
    return "\n".join(lines)


@router.get("/analyze/status")
def analyze_status():
    return {"llm_available": available(), "model": None}


PROMPTS = {
    "en": {
        "system": (
            "You are a senior OSINT intelligence analyst producing a detailed situation "
            "report from structured GDELT event data. Be analytical and specific, cite "
            "actors and places from the data, but never invent facts beyond it. "
            "CRITICAL: write your ENTIRE response in English."
        ),
        "user": (
            "Region scope: {scope}. Most salient recent events ({n} total):\n{data}\n\n"
            "Write a rich intelligence brief with these sections (use Markdown headers):\n"
            "## Executive summary — 4-6 sentences on the overall situation.\n"
            "## Key actors — bullet list, each with a one-line role/behaviour note.\n"
            "## Dynamics & trends — cooperation vs conflict balance, tone shifts, "
            "recurring interaction patterns.\n"
            "## Hotspots — the most active or tense locations, with why.\n"
            "## Escalation risk — LOW / MEDIUM / HIGH, with a substantiated 2-3 sentence rationale.\n"
            "## Monitoring recommendations — 3-5 concrete things an analyst should watch next.\n\n"
            "Write the ENTIRE response in English. Be thorough."
        ),
        "no_llm": "Local LLM (llama-server) is unreachable on :8080.",
        "no_events": "No events match the current filter.",
    },
    "fr": {
        "system": (
            "Tu es analyste senior en renseignement de sources ouvertes (OSINT). Tu produis "
            "un rapport de situation détaillé à partir de données d'événements GDELT structurées. "
            "Sois analytique et précis, cite les acteurs et lieux présents dans les données, "
            "mais n'invente jamais de faits au-delà de celles-ci. "
            "IMPÉRATIF : rédige TOUTE ta réponse en FRANÇAIS, sans un seul mot d'anglais."
        ),
        "user": (
            "Zone concernée : {scope}. Événements récents les plus saillants ({n} au total) :\n{data}\n\n"
            "Rédige une synthèse de renseignement riche avec ces sections (titres Markdown) :\n"
            "## Résumé exécutif — 4 à 6 phrases sur la situation d'ensemble.\n"
            "## Acteurs clés — liste à puces, chacun avec une note d'une ligne sur son rôle/comportement.\n"
            "## Dynamiques et tendances — équilibre coopération/conflit, évolutions de tonalité, "
            "schémas d'interaction récurrents.\n"
            "## Points chauds — les lieux les plus actifs ou tendus, et pourquoi.\n"
            "## Risque d'escalade — FAIBLE / MOYEN / ÉLEVÉ, avec une justification argumentée de 2-3 phrases.\n"
            "## Recommandations de surveillance — 3 à 5 éléments concrets à suivre en priorité.\n\n"
            "Rédige TOUTE la réponse en FRANÇAIS. Sois détaillé et complet."
        ),
        "no_llm": "Le LLM local (llama-server) est injoignable sur :8080.",
        "no_events": "Aucun événement ne correspond au filtre actuel.",
    },
}


@router.get("/analyze/brief")
def brief(
    db: Session = Depends(get_db),
    quad_class: int | None = None,
    country: str | None = None,
    actor: str | None = None,
    lang: str = Query("fr"),
    limit: int = Query(60, le=150),
):
    p = PROMPTS.get(lang, PROMPTS["fr"])
    if not available():
        return {"brief": p["no_llm"], "n": 0}

    q = select(Event).where(Event.lat.isnot(None))
    q = _apply_filters(q, quad_class, None, country, actor, None)
    q = q.order_by(Event.num_mentions.desc().nullslast(), Event.date_added.desc()).limit(limit)
    events = db.execute(q).unique().scalars().all()

    if not events:
        return {"brief": p["no_events"], "n": 0}

    scope = country.upper() if country else ("le monde" if lang == "fr" else "the world")
    data = _format_events(events)

    # Cross-source context: active GDACS disaster alerts (Orange/Red)
    dq = select(Disaster).where(Disaster.alert_level.in_(["Orange", "Red"]))
    if country:
        dq = dq.where(Disaster.country.ilike(f"%{country}%"))
    disasters = db.execute(dq.limit(12)).scalars().all()
    if disasters:
        header = (
            "\n\nAlertes catastrophes actives (GDACS) :"
            if lang == "fr"
            else "\n\nActive disaster alerts (GDACS):"
        )
        data += header + "\n" + "\n".join(
            f"- [{d.alert_level}] {d.name or d.event_type} — {d.country or '?'}" for d in disasters
        )

    messages = [
        {"role": "system", "content": p["system"]},
        {
            "role": "user",
            "content": p["user"].format(scope=scope, n=len(events), data=data),
        },
    ]
    text = chat(messages, temperature=0.35, max_tokens=1800)
    return {"brief": text, "n": len(events), "scope": scope, "lang": lang}
