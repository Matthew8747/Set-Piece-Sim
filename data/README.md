# Data lake layout

Three-layer layout per [docs/04-data-pipeline.md](../docs/04-data-pipeline.md).
**Contents are git-ignored** (size + source licensing); only this README and
`.gitkeep` markers are committed. Everything here is rebuildable from sources
via the `restart-etl` CLI (arrives in Phase 4).

| Layer | Contents | Guarantee |
|---|---|---|
| `raw/` | Byte-exact source payloads + fetch manifests (url, sha256, fetched_at, license) | Immutable, never edited |
| `staging/` | Typed Parquet, standardized units and the canonical 105x68 m coordinate frame | Schema-validated |
| `marts/` | Analysis-ready products loaded into Postgres (xG training table, calibration targets, profiles) | License-audited in CI |

Licensing: StatsBomb Open Data requires attribution and prohibits raw
redistribution - which is why `raw/` is never committed. See the licensing
audit in docs/04-data-pipeline.md §2.
