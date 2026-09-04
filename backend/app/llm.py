"""Thin client for any OpenAI-compatible chat-completions endpoint.

Defaults to the local llama-server; set settings.llm_api_key to point the analyst
at OpenAI / OpenRouter / Together / Groq / Anthropic-compatible gateways, etc."""

import requests

from app.config import settings


def headers() -> dict:
    h = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        h["Authorization"] = f"Bearer {settings.llm_api_key}"
    return h


def chat(messages, temperature: float = 0.3, max_tokens: int = 800, timeout: int = 180) -> str:
    r = requests.post(
        f"{settings.llm_base_url}/chat/completions",
        headers=headers(),
        json={
            "model": settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def available() -> bool:
    # a key-based external endpoint is assumed reachable (no health route to probe)
    if settings.llm_api_key:
        return True
    try:
        base = settings.llm_base_url.rsplit("/v1", 1)[0]
        return requests.get(f"{base}/health", timeout=5).ok
    except requests.RequestException:
        return False
