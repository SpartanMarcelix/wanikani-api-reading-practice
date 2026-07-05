"""Thin WaniKani API v2 client with pagination.

Only what Phase 1 needs: fetch started kanji+vocab assignments, and fetch the
subjects they reference. The token is read from the environment and sent as a
Bearer header; it is never logged.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import httpx

from wk_reading import config


class WaniKaniClient:
    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        self._token = token or config.get_token()
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Wanikani-Revision": config.WK_REVISION,
            },
        )

    def __enter__(self) -> "WaniKaniClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _get(self, url: str, params: dict | None = None) -> dict:
        """GET a single page, retrying politely on rate limits (HTTP 429)."""
        for attempt in range(5):
            resp = self._client.get(url, params=params)
            if resp.status_code == 429:
                # WaniKani allows 60 req/min; back off and retry.
                wait = int(resp.headers.get("Retry-After", "2"))
                time.sleep(max(wait, 1))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("Rate limited by WaniKani after several retries.")

    def _paginate(self, endpoint: str, params: dict) -> Iterator[dict]:
        """Yield every `data` element across all pages of a collection."""
        url = f"{config.WK_API_BASE}/{endpoint}"
        first = True
        while url:
            page = self._get(url, params=params if first else None)
            yield from page.get("data", [])
            url = page.get("pages", {}).get("next_url")
            first = False

    def fetch_started_assignments(self) -> list[dict]:
        """Started, non-hidden kanji + vocabulary assignments (the active pool)."""
        params = {
            "subject_types": "kanji,vocabulary",
            "started": "true",
            "hidden": "false",
        }
        return list(self._paginate("assignments", params))

    def fetch_subjects_by_ids(self, subject_ids: list[int]) -> list[dict]:
        """Fetch subjects for the given ids, chunked to keep URLs a safe length."""
        results: list[dict] = []
        chunk_size = 100
        for start in range(0, len(subject_ids), chunk_size):
            chunk = subject_ids[start : start + chunk_size]
            ids_param = ",".join(str(i) for i in chunk)
            results.extend(self._paginate("subjects", {"ids": ids_param}))
        return results
