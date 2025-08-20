"""
Intentional N+1 query example and a batched alternative.
This file is used by scalability/architecture benchmarks to detect data-access smells.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from time import sleep
from typing import Dict, Iterable, Iterator, List, Optional


@dataclass(frozen=True)
class Author:
    id: int
    name: str


@dataclass(frozen=True)
class Post:
    id: int
    author_id: int
    title: str


# Tiny in-memory "database"
AUTHORS: Dict[int, Author] = {
    1: Author(id=1, name="Ada"),
    2: Author(id=2, name="Linus"),
    3: Author(id=3, name="Guido"),
}

POSTS: List[Post] = [
    Post(id=1, author_id=1, title="Turing complete thoughts"),
    Post(id=2, author_id=2, title="Kernel notes"),
    Post(id=3, author_id=3, title="On the benevolent dictator"),
    Post(id=4, author_id=1, title="Computation and you"),
]


def get_all_posts() -> List[Post]:
    """Return all posts from the in-memory store."""
    return list(POSTS)


# Internal helpers to centralize DB access behavior and error handling
def _simulate_db_query_delay() -> None:
    """Introduce a tiny simulated DB delay. Raises RuntimeError on unexpected failures."""
    try:
        sleep(0.001)
    except Exception as exc:
        raise RuntimeError("Simulated DB delay failed") from exc


def _get_author_from_store(author_id: int) -> Optional[Author]:
    """Directly access the in-memory AUTHORS store with error wrapping."""
    try:
        return AUTHORS.get(author_id)
    except Exception as exc:
        raise RuntimeError(f"Error accessing author store for id={author_id}") from exc


def _batch_retrieve_authors(author_ids: Iterable[int]) -> Dict[int, Author]:
    """Batched retrieval from the in-memory AUTHORS store with error handling."""
    try:
        unique_ids = set(author_ids)
    except Exception as exc:
        raise RuntimeError("Invalid author_ids iterable provided to batch retrieval") from exc

    try:
        return {aid: AUTHORS[aid] for aid in unique_ids if aid in AUTHORS}
    except Exception as exc:
        raise RuntimeError("Batched author retrieval failed") from exc


def get_author_by_id(author_id: int) -> Optional[Author]:
    """
    Simulate a per-row query.

    This function intentionally simulates latency to amplify N+1 effects in profiling.
    Errors during the simulated DB access are wrapped in RuntimeError for clarity.
    """
    try:
        _simulate_db_query_delay()
        return _get_author_from_store(author_id)
    except RuntimeError:
        # Re-raise RuntimeError from helpers without alteration
        raise
    except Exception as exc:
        raise RuntimeError(f"Unexpected error retrieving author id={author_id}") from exc


def get_authors_by_ids(author_ids: Iterable[int]) -> Dict[int, Author]:
    """
    Simulate a batched query for multiple authors.

    Accepts any iterable of ints and returns a dict mapping found author ids to Author instances.
    Errors are converted to RuntimeError to make failures explicit to callers.
    """
    try:
        return _batch_retrieve_authors(author_ids)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("Unexpected error during batched author retrieval") from exc


def load_posts_with_authors_n_plus_one() -> List[Dict[str, object]]:
    """
    N+1 pattern: fetch posts, then fetch each author individually inside the loop.
    This function is intentionally inefficient for benchmark detection.
    """
    result: List[Dict[str, object]] = []
    for post in get_all_posts():
        author = get_author_by_id(post.author_id)  # N+1 per post
        result.append({"post": post, "author": author})
    return result


def load_posts_with_authors_prefetched() -> List[Dict[str, object]]:
    """Optimized version using a batched author lookup."""
    posts = get_all_posts()
    author_map = get_authors_by_ids(p.author_id for p in posts)
    # Use a generator expression to reduce peak memory when constructing the intermediate sequence.
    return list(({"post": p, "author": author_map.get(p.author_id)} for p in posts))


# Additional helpers to give benchmarks more signal

@lru_cache(maxsize=16)
def get_author_cached(author_id: int) -> Optional[Author]:
    """Cached variant that still calls the per-row getter (to test cache use)."""
    return get_author_by_id(author_id)


def load_posts_with_cache() -> List[Dict[str, object]]:
    """N+1 shape but slightly mitigated by an LRU cache (still suboptimal)."""
    result: List[Dict[str, object]] = []
    for post in get_all_posts():
        author = get_author_cached(post.author_id)
        result.append({"post": post, "author": author})
    return result


def iter_posts_streaming(batch_size: int = 2) -> Iterator[List[Post]]:
    """Simulate streaming/batched DB access to exercise iterator patterns."""
    items = list(get_all_posts())
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]