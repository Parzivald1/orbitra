"""Client HTTP partagé pour toutes les sources externes (NASA, ESA, CelesTrak...)."""
import httpx

from .config import USER_AGENT

_client: httpx.AsyncClient | None = None


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )
    return _client


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def get_json(url: str, params: dict | None = None):
    r = await client().get(url, params=params)
    r.raise_for_status()
    return r.json()


async def get_text(url: str, params: dict | None = None) -> str:
    r = await client().get(url, params=params)
    r.raise_for_status()
    return r.text
