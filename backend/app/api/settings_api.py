"""API-key management for the Settings page — lets someone who just cloned the repo
paste their free API keys without editing files by hand.

SECURITY: this reads/writes backend/.env and is meant for a local/trusted
deployment (e.g. behind Tailscale). It NEVER returns key values, only whether each
key is set. Keys are written to .env and applied to the running process in memory."""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api", tags=["settings"])

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

# env var -> (settings attribute, human label, where to get it)
KEY_DEFS = [
    ("GOOGLE_MAPS_KEY", "google_maps_key", "Google Maps (3D tiles)", "https://console.cloud.google.com/google/maps-apis"),
    ("FIRMS_MAP_KEY", "firms_map_key", "NASA FIRMS (fires)", "https://firms.modaps.eosdis.nasa.gov/api/map_key/"),
    ("AISSTREAM_KEY", "aisstream_key", "AISStream (vessels)", "https://aisstream.io/"),
    ("ACLED_EMAIL", "acled_email", "ACLED email", "https://developer.acleddata.com/"),
    ("ACLED_PASSWORD", "acled_password", "ACLED password", "https://developer.acleddata.com/"),
    ("SENTINELHUB_CLIENT_ID", "sentinelhub_client_id", "Copernicus CDSE client id", "https://shapps.dataspace.copernicus.eu/dashboard/"),
    ("SENTINELHUB_CLIENT_SECRET", "sentinelhub_client_secret", "Copernicus CDSE client secret", "https://shapps.dataspace.copernicus.eu/dashboard/"),
    ("SHODAN_KEY", "shodan_key", "Shodan (cyber)", "https://account.shodan.io/"),
    ("OPENSKY_CLIENT_ID", "opensky_client_id", "OpenSky client id", "https://opensky-network.org/"),
    ("OPENSKY_CLIENT_SECRET", "opensky_client_secret", "OpenSky client secret", "https://opensky-network.org/"),
    ("WINDY_KEY", "windy_key", "Windy Webcams", "https://api.windy.com/keys"),
    ("TOMTOM_KEY", "tomtom_key", "TomTom (traffic)", "https://developer.tomtom.com/"),
    ("OPENWEATHER_KEY", "openweather_key", "OpenWeatherMap (vent/temp globale)", "https://home.openweathermap.org/api_keys"),
]
_ENV_TO_ATTR = {env: attr for env, attr, _, _ in KEY_DEFS}
SECRET_ENVS = {"ACLED_PASSWORD", "SENTINELHUB_CLIENT_SECRET", "OPENSKY_CLIENT_SECRET"}


class KeyUpdate(BaseModel):
    env: str
    value: str


def _is_set(attr):
    return bool(getattr(settings, attr, "") or "")


@router.get("/settings/keys")
def list_keys():
    """Status of each API key — never the value itself."""
    return {"keys": [
        {"env": env, "label": label, "help": help_url, "set": _is_set(attr),
         "secret": env in SECRET_ENVS}
        for env, attr, label, help_url in KEY_DEFS
    ]}


def _write_env(env_name, value):
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    prefix = f"{env_name}="
    replaced = False
    for i, ln in enumerate(lines):
        if ln.strip().startswith(prefix):
            lines[i] = f"{env_name}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{env_name}={value}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


@router.post("/settings/keys")
def set_key(body: KeyUpdate):
    if settings.public_mode:
        return {"error": "key editing is disabled in public mode"}
    env_name = body.env.strip().upper()
    if env_name not in _ENV_TO_ATTR:
        return {"error": f"unknown key: {env_name}"}
    value = body.value.strip()
    _write_env(env_name, value)
    setattr(settings, _ENV_TO_ATTR[env_name], value)  # apply live, no restart
    return {"ok": True, "env": env_name, "set": bool(value)}


class LlmUpdate(BaseModel):
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None


@router.get("/settings/llm")
def get_llm():
    """LLM connection config. base_url/model are shown; the api key is write-only."""
    return {
        "base_url": settings.llm_base_url,
        "model": settings.llm_model,
        "api_key_set": bool(settings.llm_api_key),
    }


@router.post("/settings/llm")
def set_llm(body: LlmUpdate):
    if settings.public_mode:
        return {"error": "LLM editing is disabled in public mode"}
    if body.base_url is not None:
        v = body.base_url.strip().rstrip("/")
        _write_env("LLM_BASE_URL", v)
        settings.llm_base_url = v
    if body.model is not None:
        v = body.model.strip()
        _write_env("LLM_MODEL", v)
        settings.llm_model = v
    if body.api_key is not None:
        v = body.api_key.strip()
        _write_env("LLM_API_KEY", v)
        settings.llm_api_key = v
    return {"ok": True, "base_url": settings.llm_base_url, "model": settings.llm_model,
            "api_key_set": bool(settings.llm_api_key)}
