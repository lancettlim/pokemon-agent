"""Shared HTTP retry/backoff helper for pipelines/extract/*.

Every extractor's raw HTTP calls (list/detail fetches, page scrapes, image
downloads) used to call `session.get(...).raise_for_status()` directly, so a
single transient failure -- a 5xx response, a dropped connection, a timeout
-- partway through a run aborted the whole extraction with no output at all.
That's expensive for PokéAPI's roughly 1,350 sequential requests per run in
particular. `get_with_retry` centralizes retry-with-exponential-backoff (the
pattern pokeapi.py's move/ability/item lookups already had one bespoke copy
of) so every extractor's request path gets it uniformly.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import requests

DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0


@dataclass
class RequestStats:
    """Logical-request counters for one `track_requests()` scope. One
    `get_with_retry` call is one logical request regardless of how many
    raw retry attempts it took internally -- `attempted` counts calls that
    were made, `succeeded` counts the ones that returned a response
    without exhausting retries. Backs backlog.md #48's generated
    reports/validation/extraction_summary.json."""

    attempted: int = 0
    succeeded: int = 0
    failed_urls: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float | None:
        if self.attempted == 0:
            return None
        return self.succeeded / self.attempted


# Stack (not a single slot) so a nested track_requests() scope -- none exist
# today, but the extractors are plain functions callers could compose --
# still attributes requests to its own innermost tracker rather than
# silently falling back to an outer one.
_stats_stack: list[RequestStats] = []


@contextmanager
def track_requests() -> Iterator[RequestStats]:
    """Context manager collecting RequestStats for every `get_with_retry`
    call made anywhere during the `with` block, regardless of which
    extractor module makes it -- every extractor's raw HTTP calls already
    funnel through this one function, so this is the natural place to
    instrument request counts without touching extractor internals."""
    stats = RequestStats()
    _stats_stack.append(stats)
    try:
        yield stats
    finally:
        _stats_stack.pop()


def get_with_retry(
    session: requests.Session,
    url: str,
    *,
    attempts: int = DEFAULT_RETRY_ATTEMPTS,
    backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
    on_rate_limited: Callable[[requests.Response], None] | None = None,
    **kwargs,
) -> requests.Response:
    """GET url, retrying transient failures (connection errors, timeouts, 5xx
    responses) with exponential backoff. A 4xx response fails immediately --
    retrying a client error just burns the backoff window on a request that
    will never succeed -- except a 429 when `on_rate_limited` is given: it
    is called with the response (to wait out the server's window) and the
    request is retried, still one logical request in the stats.

    Raises the last exception once `attempts` is exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, **kwargs)
            response.raise_for_status()
            if _stats_stack:
                _stats_stack[-1].attempted += 1
                _stats_stack[-1].succeeded += 1
            return response
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 429 and on_rate_limited is not None and attempt < attempts - 1:
                on_rate_limited(exc.response)
                last_exc = exc
                continue
            if exc.response is not None and exc.response.status_code < 500:
                if _stats_stack:
                    _stats_stack[-1].attempted += 1
                    _stats_stack[-1].failed_urls.append(url)
                raise
            last_exc = exc
        except requests.exceptions.RequestException as exc:
            last_exc = exc
        if attempt < attempts - 1:
            delay = backoff_seconds * (2**attempt)
            print(
                f"Transient error fetching {url} "
                f"(attempt {attempt + 1}/{attempts}): {last_exc}; retrying in {delay:.0f}s",
                file=sys.stderr,
            )
            time.sleep(delay)
    if _stats_stack:
        _stats_stack[-1].attempted += 1
        _stats_stack[-1].failed_urls.append(url)
    raise last_exc
