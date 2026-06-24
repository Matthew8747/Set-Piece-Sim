"""StatsBomb Open Data fetcher (raw layer).

Pulls competitions -> matches -> per-match events + lineups as byte-exact JSON
into ``data/raw/statsbomb`` and records every file in the manifest. We fetch the
raw GitHub-hosted JSON directly (no ``statsbombpy`` dependency): fewer moving
parts, and the cache is exactly the published bytes, which is what the
reproducibility gate hashes.

``ASSUMPTION D-1`` (doc 04 §2): StatsBomb Open Data remains available under
current terms; the raw cache is downloaded once and kept locally (permitted for
use, not redistribution - hence git-ignored).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx

from restart_etl.config import STATSBOMB_LICENSE, Competition, DataPaths
from restart_etl.raw import Manifest, make_entry, manifest_path, save_manifest, write_cached

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

ProgressFn = Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover - default progress sink
    pass


class StatsBombFetcher:
    """Fetches and caches StatsBomb Open Data for an allow-listed competition set."""

    def __init__(
        self,
        paths: DataPaths,
        *,
        client: httpx.Client | None = None,
        progress: ProgressFn | None = None,
    ) -> None:
        self._paths = paths
        self._root = paths.root
        self._dir = paths.statsbomb_raw
        self._client = client if client is not None else httpx.Client(timeout=30.0)
        self._owns_client = client is None
        self._progress = progress if progress is not None else _noop
        self._manifest = Manifest(source="statsbomb_open_data")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> StatsBombFetcher:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ fetch
    def _get(self, url: str, dest: Path) -> bytes:
        resp = self._client.get(url)
        resp.raise_for_status()
        data = resp.content
        write_cached(dest, data)
        self._manifest.entries.append(
            make_entry(
                repo_root=self._root,
                dest=dest,
                url=url,
                data=data,
                license=STATSBOMB_LICENSE,
            )
        )
        return data

    def fetch(self, competitions: list[Competition]) -> Manifest:
        """Fetch the competitions allow-list; returns the written manifest."""
        self._paths.ensure()

        comp_url = f"{BASE_URL}/competitions.json"
        self._progress("competitions.json")
        self._get(comp_url, self._dir / "competitions.json")

        for comp in competitions:
            self._progress(f"matches {comp.alias} ({comp.competition_id}/{comp.season_id})")
            matches_url = f"{BASE_URL}/matches/{comp.competition_id}/{comp.season_id}.json"
            dest = self._dir / "matches" / f"{comp.competition_id}_{comp.season_id}.json"
            matches_raw = self._get(matches_url, dest)
            matches = json.loads(matches_raw)
            match_ids = [int(m["match_id"]) for m in matches]
            self._progress(f"  {len(match_ids)} matches in {comp.alias}")

            for i, mid in enumerate(match_ids, start=1):
                if i % 10 == 0 or i == len(match_ids):
                    self._progress(f"  events/lineups {i}/{len(match_ids)} ({comp.alias})")
                self._get(f"{BASE_URL}/events/{mid}.json", self._dir / "events" / f"{mid}.json")
                self._get(f"{BASE_URL}/lineups/{mid}.json", self._dir / "lineups" / f"{mid}.json")

        save_manifest(manifest_path(self._dir), self._manifest)
        return self._manifest
