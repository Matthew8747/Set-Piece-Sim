# Going live: a step-by-step plan

This is the runbook for putting Restart Lab in front of people, plus the decision behind it.

## The decision: ship a live demo *and* keep the repo excellent

The honest worry is cost: the simulation is CPU-heavy. But the heavy part and the interactive part
are already separated by design, so a hosted demo is cheap and safe:

- **The optimization studies are precomputed.** The `/optimize` pages read a committed `study.json`
  as static data. The optimizer (Optuna, LightGBM, SHAP) never runs inside a web request. Serving
  these pages costs effectively zero compute.
- **The workbench runs small, bounded simulations on demand.** A single delivery or a 200-sim Monte
  Carlo batch finishes in seconds. The API already caps this: `n_sims` is bounded, reads are limited
  to 120/min and writes to 20/min per IP, and at most 2 jobs run at once (`max_concurrent_jobs`).
- **The host scales to zero.** On Fly.io the backend machine stops when idle and starts on the next
  request, so an idle demo costs nothing.

So the recommendation is **both**:

1. A **live demo** (Vercel for the web app, Fly.io for the API) so there is a clickable link for a CV,
   LinkedIn post, or portfolio. This is the single highest-value thing you can do with the project.
2. A **polished GitHub repo** for the people who read code: a clear README, the ADRs, and a recorded
   demo so the depth is visible without anyone running it.

If you would rather not host anything, the GitHub-only path is at the bottom and is still a strong
portfolio piece.

## What the public sees

Lead with the surface that costs nothing and looks best:

- **`/optimize`** is the hero. Convergence, the parallel-coordinates trial cloud, the SHAP insights,
  the honesty banner. All precomputed, zero compute, nothing to break.
- **`/scenarios`** (the workbench) is the interactive proof. Keep the default sim size small and the
  rate limits on. Optionally set an API key so only you can trigger writes, and let visitors read.

## Step by step

### 1. Pre-flight (local)

- [ ] Run the full gate: `./scripts/verify.sh` (or `powershell -File scripts/verify.ps1`). Everything
      green.
- [ ] Decide the public surface: optimization-only, or workbench too. Optimization-only needs no squad
      data and is the simplest first launch.

### 2. Data (only if you expose the workbench)

The squads and the xG model come from the StatsBomb-derived marts, which are not committed (the data
is not redistributed). Build them where the app runs, not by uploading them:

- [ ] Run the ETL to produce `data/marts` (see [etl-runbook.md](etl-runbook.md)).
- [ ] After the backend is up, upload the marts to its Fly volume (`fly sftp` or rebuild on the volume).
- The `/optimize` surface needs none of this; it ships in the image.

### 3. Backend to Fly.io

- [ ] Install flyctl and `fly auth login`.
- [ ] Edit the app name in [`fly.toml`](../fly.toml).
- [ ] `fly launch --no-deploy` to create the app.
- [ ] `fly volumes create restart_data --size 1 --region lhr` for the marts + SQLite store.
- [ ] `fly secrets set RESTART_CORS_ORIGINS='["https://YOUR-APP.vercel.app"]'` (you can fill the real
      URL after step 4 and re-set it).
- [ ] `fly deploy`.
- [ ] Smoke test: `curl https://your-api.fly.dev/healthz` returns the engine version.

Optional, only when you outgrow the server-free default:

- [ ] Provision **Neon** Postgres, then `fly secrets set RESTART_DATABASE_URL='postgresql+psycopg://…'`.
- [ ] Provision **Upstash** Redis, then `fly secrets set RESTART_REDIS_URL='redis://…'` for the Arq
      worker path.

### 4. Frontend to Vercel

- [ ] Import the GitHub repo in Vercel.
- [ ] Set the project **root directory** to `apps/frontend`.
- [ ] Set env `NEXT_PUBLIC_API_BASE_URL` to the Fly API URL (and `NEXT_PUBLIC_API_KEY` if you gate
      writes).
- [ ] Deploy. Vercel auto-detects Next.js; no extra config needed.

### 5. Connect and harden

- [ ] Re-set `RESTART_CORS_ORIGINS` on Fly to the final Vercel URL, then `fly deploy`.
- [ ] Confirm the live site loads `/optimize` and `/scenarios`.
- [ ] Leave the rate limits on. If the workbench is public, keep the default sim size small.
- [ ] Set `RESTART_API_KEY` if you want writes to be yours only.

### 6. Make it count for the portfolio

- [ ] Add the live link and 3 to 4 screenshots to the README (landing, a study detail, the 3D replay).
- [ ] Record a 20 to 30 second screen capture of the optimize page and a replay; a GIF in the README
      is worth more than paragraphs.
- [ ] Write the post. The honest, strong claims: a deterministic physics and agent Monte Carlo engine;
      an optimizer that has to beat random search to report a winner; a real-data xG model; and a
      Numba throughput kernel verified to `1e-9` against the reference.

## Cost

For a portfolio demo this is effectively free: Fly's allowance with scale-to-zero, Vercel's hobby tier,
and (if used) Neon's free Postgres. The job caps and rate limits are the cost-bomb protection.

## The GitHub-only alternative

If you skip hosting entirely:

- [ ] Keep the README excellent (it is the product page).
- [ ] Add screenshots and a recorded demo GIF so the work is visible without running it.
- [ ] Make sure `Quickstart` runs clean on a fresh clone.
- [ ] Pin the repo on your profile and link it from your CV.

This is a legitimate choice. A clear repo with a demo recording communicates most of the value, with
none of the hosting overhead.
