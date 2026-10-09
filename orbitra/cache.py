"""Cache mémoire avec durée de vie.

Les API spatiales sont gratuites mais limitées (Launch Library : 15 requêtes/heure,
CelesTrak : une mise à jour toutes les 2 h). On garde donc les réponses en mémoire,
et si la source tombe on renvoie la dernière version connue plutôt qu'une erreur.
"""
import asyncio
import time
from functools import wraps


def ttl_cache(seconds: float):
    def decorator(fn):
        store: dict = {}
        locks: dict = {}

        @wraps(fn)
        async def wrapper(*args):
            hit = store.get(args)
            if hit and time.monotonic() - hit[0] < seconds:
                return hit[1]
            lock = locks.setdefault(args, asyncio.Lock())
            async with lock:
                hit = store.get(args)
                if hit and time.monotonic() - hit[0] < seconds:
                    return hit[1]
                try:
                    value = await fn(*args)
                except Exception:
                    if hit:  # mieux vaut des données un peu vieilles que rien
                        return hit[1]
                    raise
                store[args] = (time.monotonic(), value)
                return value

        wrapper.cache_clear = store.clear
        return wrapper

    return decorator
