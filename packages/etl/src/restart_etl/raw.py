"""Raw layer: byte-exact source cache + fetch manifest.

The raw layer is immutable and git-ignored (size + license). Every file pulled
from a source is hashed and recorded in ``manifest.json`` with its url, sha256,
byte count, fetch timestamp, and license string - so a frozen raw snapshot is
content-addressable and the reproducibility gate (doc 04 §5) can assert stable
hashes. Nothing here is ever edited in place; a re-fetch overwrites and the
manifest is rewritten.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ManifestEntry(BaseModel):
    """One cached raw payload."""

    model_config = {"frozen": True}

    path: str  # repo-relative path of the cached file
    url: str  # source URL it was fetched from
    sha256: str
    bytes: int
    fetched_at: str  # ISO-8601 UTC
    license: str


class Manifest(BaseModel):
    """The full raw-cache manifest for one source."""

    source: str
    entries: list[ManifestEntry] = Field(default_factory=list)

    def content_hash(self) -> str:
        """Stable hash over (path, sha256) pairs - the frozen-snapshot fingerprint.

        Order-independent: entries are sorted so a re-fetch in a different order
        yields the same fingerprint for identical bytes.
        """
        h = hashlib.sha256()
        for e in sorted(self.entries, key=lambda x: x.path):
            h.update(e.path.encode())
            h.update(e.sha256.encode())
        return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_cached(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def make_entry(
    *, repo_root: Path, dest: Path, url: str, data: bytes, license: str
) -> ManifestEntry:
    return ManifestEntry(
        path=dest.relative_to(repo_root).as_posix(),
        url=url,
        sha256=sha256_bytes(data),
        bytes=len(data),
        fetched_at=datetime.now(UTC).isoformat(),
        license=license,
    )


def manifest_path(statsbomb_raw: Path) -> Path:
    return statsbomb_raw / "manifest.json"


def save_manifest(path: Path, manifest: Manifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.model_dump(), indent=2, sort_keys=True), encoding="utf-8")


def load_manifest(path: Path) -> Manifest:
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))
