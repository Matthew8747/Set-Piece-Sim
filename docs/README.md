# Restart Lab — Design Documentation

**AI-Assisted Set-Piece Optimization for International Football (FIFA World Cup 2026)**

> "Restart" is the coaching term for any dead-ball resumption of play — corners, free kicks,
> throw-ins. This platform simulates and optimizes them.

This directory is the design package for the platform. Read in order:

| # | Document | Purpose |
|---|----------|---------|
| 1 | [Product Requirements Document](01-prd.md) | What we are building, for whom, and why |
| 2 | [System Architecture](02-system-architecture.md) | Components, boundaries, tech stack, deployment |
| 3 | [Database Schema](03-database-schema.md) | Entities, relations, DDL, storage strategy |
| 4 | [Data Pipeline Design](04-data-pipeline.md) | Sources, licensing, ETL, data quality |
| 5 | [Simulation Architecture](05-simulation-architecture.md) | Physics, agents, tactics, Monte Carlo, validation |
| 6 | [Machine Learning Architecture](06-ml-architecture.md) | xG models, routine optimization, explainability |
| 7 | [UI/UX Design Plan](07-ui-ux-design.md) | Design language, information architecture, visualization |
| 8 | [12-Week Development Roadmap](08-roadmap.md) | Phases, milestones, acceptance criteria, cut lines |

## Status

- **Stage:** Design review (no implementation code yet, by design)
- **Next gate:** Stakeholder review of this package → implementation plan → Phase 0

## Document conventions

- Every phase in the roadmap specifies: Goals, Deliverables, Architecture decisions, Risks,
  Alternatives considered, Documentation required, Acceptance criteria.
- Decisions that reverse easily are marked **(reversible)**; one-way doors are marked **(commit)**.
- Assumptions the design depends on are tagged `ASSUMPTION:` and indexed in each document.
