# Restart Lab - Design Documentation

**AI-Assisted Set-Piece Optimization for International Football (FIFA World Cup 2026)**

> "Restart" is the coaching term for any dead-ball resumption of play - corners, free kicks,
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

## Living guides (kept current with the implementation)

| Document | Purpose |
|---|---|
| [Setup Guide](setup-guide.md) | Zero → verified local environment |
| [Development Guide](development-guide.md) | Commands, conventions, architecture rules, tech-debt register |
| [Simulation Assumptions Registry](simulation-assumptions.md) | Every physics assumption (P-1…P-15): value, citation, calibration status, validation evidence |
| [ADRs](adr/README.md) | Architectural decision records (build-vs-buy, integration strategy) |
| [../CONTRIBUTING.md](../CONTRIBUTING.md) | Workflow and review standards |
| [../CHANGELOG.md](../CHANGELOG.md) | Per-phase change history |

## Status

- **Stage:** Phase 1 (ball physics core, `sim/0.1.0`) complete on `feat/phase1-physics-core`
- **Next gate:** Phase 1 review → Phase 2 (agents & tactical engine, roadmap Phase 2)

## Document conventions

- Every phase in the roadmap specifies: Goals, Deliverables, Architecture decisions, Risks,
  Alternatives considered, Documentation required, Acceptance criteria.
- Decisions that reverse easily are marked **(reversible)**; one-way doors are marked **(commit)**.
- Assumptions the design depends on are tagged `ASSUMPTION:` and indexed in each document.
