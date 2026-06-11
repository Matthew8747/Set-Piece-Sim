# Restart Lab

**AI-assisted set-piece optimization for international football — built around the FIFA World Cup 2026.**

A physics-grounded simulator, agent-based player models, Monte Carlo experimentation, and
machine-learning-driven routine search, wrapped in an analyst-grade web platform. The question
it answers: *given our players and their defenders, what is the highest-value way to take this
corner, free kick, or throw-in?*

## Status

🏗️ **Design phase.** The complete design package — PRD, system architecture, database schema,
data pipeline, simulation architecture, ML architecture, UI/UX plan, and 12-week roadmap — lives
in [`docs/`](docs/README.md). Implementation begins after design review.

## The 60-second pitch

- **Simulate**: a vectorized physics engine (drag, Magnus, bounce) plus kinematically honest
  player agents play out a set piece 10,000 times in under a minute.
- **Measure**: goal/shot/first-contact probabilities with confidence intervals, scored by
  xG models trained on real World Cup and Euros data (StatsBomb Open Data).
- **Optimize**: Bayesian optimization searches the routine space — delivery, runs, screens,
  timing — and explains *why* the winners win.
- **Calibrate honestly**: simulated outcome rates are gated against real-world base rates
  before any predictive claim is made.

## License & data

Code license TBD at first release. Uses [StatsBomb Open Data](https://github.com/statsbomb/open-data)
under its non-commercial research terms, with attribution. No proprietary ratings data is used;
every player attribute is provenance-tagged. This is a research/portfolio project and is not
affiliated with FIFA or any national federation.
