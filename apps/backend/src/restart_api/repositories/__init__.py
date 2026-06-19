"""Persistence ports and adapters (ADR-007 d1).

Ports are Protocols; the default adapters are file-based (server-free CI/dev),
with Postgres drop-ins implementing the same Protocols for production.
"""
