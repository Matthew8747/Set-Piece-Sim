# Go Live — the only runbook you need

**Goal:** turn the "TypeError: Failed to fetch" Vercel deploy into a working live demo.

## Why it's broken right now

The frontend is the only thing deployed. Every page — including `/optimize` — fetches its data
from the backend API. With no backend, the browser falls back to the built-in default
(`http://localhost:8000`), which doesn't exist in production, so every request fails:

> `TypeError: Failed to fetch`

There is no code bug. Two pieces of config are missing:

1. **The backend isn't deployed.** It runs on Fly.io (FastAPI in a container). Nothing is there yet.
2. **Vercel doesn't know the backend URL.** `NEXT_PUBLIC_API_BASE_URL` is unset, so the frontend
   talks to `localhost`.

Fix both and the site works. Everything below is one-time setup. Steps you must do by hand are
tagged **🔴 MANUAL** (account login, dashboard clicks, picking names). Nothing here needs a code
change.

## What's already done for you

- `fly.toml` + `apps/backend/Dockerfile` are written and current. The image **bakes in everything
  the demo needs**: the committed optimization study, the squad/xG marts (`data/marts/*.parquet`),
  and the xG model (`models/`). **No Fly volume, no ETL, no database, no Redis.** It boots on
  SQLite + an in-process job queue and the host scales to zero when idle (cost ≈ £0).
- The frontend is a standard Next.js app. Vercel auto-detects it; the only settings are the root
  directory and one env var.

---

## The one warning that bites people

> **Deploy the backend with `fly deploy` from your own machine — this directory.**

The squad/xG marts under `data/marts/` are git-ignored (the StatsBomb-derived data isn't
redistributed), but they **are** baked into the image. `fly deploy` uploads your *local* working
directory as the build context, so the marts on your disk get baked in. A build triggered from
GitHub would not have them and `/scenarios` would come up empty. So: run `fly deploy` locally, from
this repo, where `data/marts/*.parquet` exist. (Confirm with `ls data/marts` — you should see five
`.parquet` files.)

`/optimize` does **not** depend on the marts — its study is committed — so even in the worst case
that surface always works.

---

## Backend → Fly.io

🔴 **MANUAL — one-time account + CLI:**

```bash
# 1. Install flyctl, then log in (opens a browser).
fly auth login

# 2. Create the app from the existing fly.toml. Pick a name (or keep restart-lab-api
#    if it's free); note the name it gives you — your URL is https://<name>.fly.dev.
fly launch --no-deploy --copy-config

# 3. Deploy. Run this from THIS repo so the marts get baked in (see the warning above).
fly deploy

# 4. Smoke test — should print the engine version, not an error.
curl https://<your-app>.fly.dev/healthz
```

Leave `RESTART_CORS_ORIGINS` for now — you set it after you know the Vercel URL (last section).

---

## Frontend → Vercel

🔴 **MANUAL — in the Vercel dashboard for your imported project:**

1. **Settings → General → Root Directory:** set to `apps/frontend`.
   (The repo is an npm workspace; Vercel finds the lockfile at the repo root and installs the whole
   workspace, so the `@restart/shared-types` / `@restart/pitch-kit` deps resolve. Don't override the
   install command.)
2. **Settings → Environment Variables:** add
   - `NEXT_PUBLIC_API_BASE_URL` = `https://<your-app>.fly.dev`  *(your Fly URL from above, no
     trailing slash)*
3. **Deployments → Redeploy** (env vars only apply to a fresh build).

That's the whole frontend config — no `vercel.json`, no build tweaks.

---

## Connect the two (CORS) — do this last

The backend must allow the browser origin, and you only know the final Vercel URL after the step
above.

🔴 **MANUAL:**

```bash
# Use your real Vercel production URL. JSON-list syntax, exact origin, no trailing slash.
fly secrets set RESTART_CORS_ORIGINS='["https://YOUR-PROJECT.vercel.app"]'
fly deploy
```

Then open the Vercel URL: `/optimize` and `/scenarios` should both load. Done — it's live.

---

## Optional hardening (skip for a first launch)

- **Lock writes to you only.** Generate a key and set it on both sides so visitors can read and run
  small sims, but only you trigger writes:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"   # generate, don't invent
  fly secrets set RESTART_API_KEY='<that key>'
  ```
  Then add `NEXT_PUBLIC_API_KEY=<that key>` in Vercel and redeploy. Leave both unset for an open
  demo — the rate limits (120 reads/min, 20 writes/min per IP) and the 2-job cap already protect it.
- **Scale out** (only if you outgrow the server-free default): provision Neon Postgres and Upstash
  Redis, then `fly secrets set RESTART_DATABASE_URL=…` and `RESTART_REDIS_URL=…`. The same image
  picks them up at runtime. Not needed for a portfolio demo.

## Cost

Effectively free: Fly's allowance with scale-to-zero, Vercel's hobby tier. The job caps and rate
limits are the cost-bomb protection.
