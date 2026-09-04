from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Public deployment hardening: disables the API-key/LLM editing routes and
    # rate-limits the AI chat. Set PUBLIC_MODE=1 in production.
    public_mode: bool = False
    chat_rate_per_min: int = 8  # analyst requests per IP per minute when public

    database_url: str = "postgresql+psycopg://osint:osint@localhost:5544/osint"
    gdelt_lastupdate_url: str = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
    ingest_loop_seconds: int = 900

    # LLM (any OpenAI-compatible endpoint). Default = local llama-server (no key).
    # Set llm_api_key to use OpenAI, OpenRouter, Together, Groq, etc.
    llm_base_url: str = "http://localhost:8080/v1"
    llm_model: str = "Qwen3-Coder-Next-Q4_K_M.gguf"
    llm_api_key: str = ""

    # Google Maps Platform key (Photorealistic 3D Tiles). Set in backend/.env.
    google_maps_key: str = ""

    # NASA FIRMS (active fire detections, global). Free MAP_KEY in backend/.env.
    firms_map_key: str = ""
    firms_source: str = "VIIRS_SNPP_NRT"

    # ACLED (armed conflict events). OAuth with myACLED account (Research tier+).
    acled_email: str = ""
    acled_password: str = ""
    acled_token_url: str = "https://acleddata.com/oauth/token"
    acled_read_url: str = "https://acleddata.com/api/acled/read"

    # AISStream (real-time vessel AIS positions). Free key in backend/.env.
    aisstream_key: str = ""

    # Sentinel Hub / Copernicus (satellite imagery). OAuth client in backend/.env.
    sentinelhub_client_id: str = ""
    sentinelhub_client_secret: str = ""

    # Shodan (cyber exposure). Free key in backend/.env.
    shodan_key: str = ""

    # OpenSky (ADS-B flights). OAuth client credentials (higher rate limits).
    opensky_client_id: str = ""
    opensky_client_secret: str = ""

    # Windy Webcams (public geolocated live webcams). Free key in backend/.env.
    windy_key: str = ""

    # TomTom (real-time road traffic flow tiles). Free key in backend/.env.
    tomtom_key: str = ""

    # OpenWeatherMap (global wind / temperature / clouds tiles). Free key.
    openweather_key: str = ""


settings = Settings()
