# Verify the savings analysis

Adversarial audit. Your job is to find errors, not agree. Work in
`/Users/prathamprabhu/Downloads/Hackathon Mantis /hackathon-2026-official/track-2`.

Use `python3` + pandas on `data/prepped/jobs.parquet` (74,849 rows) and
`data/prepped/gpus.parquet` (96,893 rows). API on `http://localhost:8000`; if your
sandbox blocks it, read `data/synthetic/findings.json` directly instead.
Prices: $2.50/GPU-hour, $95/engineer-hour, $0.15/kWh. Cluster total = 594,004 GPU-hours.

**Recompute each claim your own way. Do NOT read `analysis/a6_savings.py`** or you will
inherit our method and our mistakes.

Answer each as one line: `CLAIM <n>: CONFIRMED <value>` / `WRONG <yours> vs <ours>` /
`CANNOT VERIFY <why>`.

## Claims

1. Jobs with `gpu_count >= 9`: **398 jobs, 98,473 GPU-h** (16.6% of cluster).
2. Of those, with `sm_util_avg < 5` AND `walltime_sec >= 3600`: **31 jobs, 16,925 GPU-h
   ($42,313)**. Also: their median `walltime_sec` is about **12.5 hours**.
3. **Critical check.** Drop the `walltime_sec >= 3600` filter and the same query returns
   **233 jobs but only 17,226 GPU-h**, with a median walltime of about **95 seconds**.
   Confirm that removing the duration filter multiplies the job count ~7.5x while adding
   under 2% more GPU-hours. (We use this to argue the unfiltered count is misleading.)
4. Within claim 2's 31 jobs, **one user owns about 16,080 of the 16,925 GPU-h (95%)
   across 25 jobs**.
5. Jobs with `gpu_count >= 9` and `sm_util_avg > 80`: **36 jobs, 53,519 GPU-h**.
6. Multi-card jobs (from `gpus.parquet`, jobs with `gpu_count >= 2`): **9,828 jobs**. Of
   those, where the busiest card's `avgsmutilization_pct >= 20` and (busiest - quietest)
   > 30 points: **1,228 jobs, 26,184 GPU-h**.
7. `state_name == "TIMEOUT"`: **1,544 jobs, 107,952 GPU-h ($269,879)**. Of those with
   `sm_util_avg > 20`: **208 jobs, 48,157 GPU-h**.
8. `rules::array-mass-failure` = **149 findings**; `rules::array-task-failure` = **5,044
   findings** (about 34 per array). The unique jobs behind array-task-failure total
   **1,453 GPU-h**.
9. Total `energy_wh` across all jobs = about **46.0 MWh** = **$6,905** at $0.15/kWh. Of
   that, jobs where `state_name != "COMPLETED"` account for about **26.2 MWh (56.9%)**.
10. Right-sizing: jobs with `gpu_count >= 2`, `sm_util_avg < 10`, `gpu_hours > 10`,
    `walltime_sec >= 3600` number about **1,028**. If each such job were resized to
    `max(1, ceil(gpu_count * 0.10))` cards, freed hours = `gpu_hours * (1 - new/old)`
    summed = about **52,766 GPU-h**. Verify the arithmetic AND tell us whether you think
    this model is defensible.
11. Sanity: no single figure above exceeds 594,004 GPU-hours.

## Also report

- Any claim where a different defensible method changes the answer materially.
- Anything stated as measurement that is really a judgment call. Be specific.
- **Claim 10 especially**: is "resize to 10% headroom" a sound way to estimate savings,
  or is it too speculative to put in front of a CFO?
- Whether excluding short jobs (claim 2 vs 3) is honest analysis or cherry-picking.

End with: `VERDICT: <n> confirmed, <n> wrong, <n> unverifiable` plus one sentence on
whether you would put these numbers in front of a CFO.
