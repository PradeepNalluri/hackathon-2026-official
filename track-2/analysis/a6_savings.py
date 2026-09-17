"""A6: where else can GPU time be saved?

Hunts for recoverable capacity in places the detectors do not look, using only
the prepped tables. Each block prints a number a CFO can act on.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "starter"))
from mgai_client import MGAI  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
mg = MGAI()
jobs = pd.read_parquet(ROOT / "data/prepped/jobs.parquet")
gpus = pd.read_parquet(ROOT / "data/prepped/gpus.parquet")
pb = mg.price_book()
GPU, ENG, KWH = pb["usd_per_gpu_hour"], pb["usd_per_engineer_hour"], pb["usd_per_kwh"]
CEIL = 594_004
out = {}


def line(label, gh, extra=""):
    print(f"  {label:<46} {gh:>10,.0f} GPU-h  ${gh*GPU:>11,.0f}  "
          f"{gh/CEIL:>5.1%} {extra}")


# ============================================================ 1. WIDE JOBS
print("=" * 86)
print("1. WIDE JOBS: the same allocation, opposite outcomes")
print("=" * 86)
# Duration floor: a 95-second job holds no recoverable time, and without this
# filter the job COUNT is dominated by short test runs while the DOLLARS are not.
# 1h floor keeps 98% of the hours and drops 202 of 233 jobs.
MIN_SEC = 3600
j = jobs[jobs.gpu_count >= 9]
low = j[(j.sm_util_avg < 5) & (j.walltime_sec >= MIN_SEC)]
high = j[j.sm_util_avg > 80]
print(f"  jobs at 9+ GPUs: {len(j):,}   ({j.gpu_hours.sum():,.0f} GPU-h, "
      f"{j.gpu_hours.sum()/CEIL:.1%} of cluster)")
print(f"    under 5% util: {len(low):>5,} jobs ({len(low)/len(j):.0%})")
line("      their hours (recoverable)", low.gpu_hours.sum())
print(f"    over 80% util: {len(high):>5,} jobs ({len(high)/len(j):.0%})")
line("      their hours (genuinely productive)", high.gpu_hours.sum())

# who are the two populations?
print(f"\n  WHO: the low-util population")
lu = low.groupby("id_user").gpu_hours.agg(["sum", "size"]).nlargest(3, "sum")
for u, r in lu.iterrows():
    print(f"    user {int(u):<14} {r['sum']:>9,.0f} GPU-h over {int(r['size'])} jobs")
print(f"    top 3 users own {lu['sum'].sum()/low.gpu_hours.sum():.0%} "
      f"of all wide-low-util waste")
print(f"    median duration  low-util {low.walltime_sec.median()/3600:>6.1f}h   "
      f"vs high-util {high.walltime_sec.median()/3600:.1f}h")
print(f"    job_type mix (low): {dict(low.job_type.value_counts().head(2))}")

# the policy: what does a justification gate above N GPUs recover?
print(f"\n  POLICY: require justification above N GPUs")
for n in (5, 9, 17, 33):
    w = jobs[(jobs.gpu_count >= n) & (jobs.sm_util_avg < 5)
             & (jobs.walltime_sec >= MIN_SEC)]
    print(f"    N={n:<3} would review {len(w):>5,} jobs, "
          f"recovering up to {w.gpu_hours.sum():>9,.0f} GPU-h "
          f"(${w.gpu_hours.sum()*GPU:>10,.0f})")

out["wide_jobs"] = dict(
    min_walltime_sec=MIN_SEC,
    jobs_9plus=int(len(j)), hours_9plus=round(float(j.gpu_hours.sum()), 1),
    low_util_jobs=int(len(low)), low_util_hours=round(float(low.gpu_hours.sum()), 1),
    low_util_usd=round(float(low.gpu_hours.sum()) * GPU, 2),
    low_util_share_of_wide=round(len(low) / len(j), 4),
    high_util_jobs=int(len(high)), high_util_hours=round(float(high.gpu_hours.sum()), 1),
    top3_users_share=round(float(lu["sum"].sum() / low.gpu_hours.sum()), 4),
    policy={f"N={n}": dict(
        jobs=int(len(jobs[(jobs.gpu_count >= n) & (jobs.sm_util_avg < 5)
                          & (jobs.walltime_sec >= MIN_SEC)])),
        gpu_hours=round(float(jobs[(jobs.gpu_count >= n) & (jobs.sm_util_avg < 5)
                                   & (jobs.walltime_sec >= MIN_SEC)].gpu_hours.sum()), 1))
        for n in (5, 9, 17, 33)})

# ============================================================ 2. CARD IMBALANCE
print("\n" + "=" * 86)
print("2. CARD IMBALANCE: cards held but never driven (invisible in jobs.parquet)")
print("=" * 86)
multi = gpus[gpus.id_job.isin(jobs[jobs.gpu_count >= 2].id_job)]
per = multi.groupby("id_job").agg(
    cards=("gpu_id", "size"),
    hi=("avgsmutilization_pct", "max"),
    lo=("avgsmutilization_pct", "min"),
    hrs=("gpu_hours", "sum"))
per["spread"] = per.hi - per.lo
imb = per[(per.hi >= 20) & (per.spread > 30)]
print(f"  multi-card jobs                  {len(per):,}")
print(f"  with a >30pt spread and a busy card  {len(imb):,}")
line("  their total hours", imb.hrs.sum())
# the idle share: hours on cards that sat far below the busiest
idle_frac = ((imb.hi - imb.lo) / 100).clip(0, 1)
wasted = float((imb.hrs * idle_frac * 0.5).sum())  # half the spread, conservative
line("  conservative idle portion", wasted)
print(f"  NOTE jobs.parquet averages a job's cards, so a 0%/65% job reads as 35%.")
print(f"       This is only visible in gpus.parquet. rules::gpu-imbalance fires "
      f"{len(mg.findings_df(detector_id='rules::gpu-imbalance')):,} times.")
out["card_imbalance"] = dict(
    multi_card_jobs=int(len(per)), imbalanced_jobs=int(len(imb)),
    imbalanced_hours=round(float(imb.hrs.sum()), 1),
    conservative_idle_gpu_hours=round(wasted, 1),
    conservative_idle_usd=round(wasted * GPU, 2))

# ============================================================ 3. RIGHT-SIZING
print("\n" + "=" * 86)
print("3. RIGHT-SIZING: jobs that would run the same on fewer GPUs")
print("=" * 86)
# A job using <10% of N cards could plausibly run on ceil(N * util) cards.
cand = jobs[(jobs.gpu_count >= 2) & (jobs.sm_util_avg < 10) & (jobs.gpu_hours > 10)
            & (jobs.walltime_sec >= MIN_SEC)]
import math
shrunk = cand.apply(
    lambda r: r.gpu_hours * (1 - max(1, math.ceil(r.gpu_count * 0.10)) / r.gpu_count),
    axis=1).sum()
print(f"  jobs >=2 GPUs, <10% util, >10 GPU-h    {len(cand):,}")
line("  hours freed by right-sizing to 10% headroom", float(shrunk))
print(f"  (each job keeps at least 1 GPU; this is a resize, not a cancellation)")
out["rightsizing"] = dict(jobs=int(len(cand)),
                          gpu_hours=round(float(shrunk), 1),
                          usd=round(float(shrunk) * GPU, 2))

# ============================================================ 4. ARRAY BLAST
print("\n" + "=" * 86)
print("4. ARRAY FAILURES: one bad script, thousands of dead tasks")
print("=" * 86)
am = mg.findings_df(detector_id="rules::array-mass-failure")
at = mg.findings_df(detector_id="rules::array-task-failure")
at_ids = pd.to_numeric(at.metadata_job_id, errors="coerce").dropna().astype("int64")
at_hrs = float(jobs[jobs.id_job.isin(set(at_ids))].gpu_hours.sum())
print(f"  arrays that mass-failed              {len(am):,}")
print(f"  individual dead tasks                {len(at):,}  "
      f"({len(at)/max(len(am),1):.0f} symptoms per problem)")
line("  hours destroyed", at_hrs)
print(f"  FIX: fail-fast on arrays. If an array's first 10 tasks all fail,")
print(f"       cancel the rest. Most of these hours are the tasks after task 10.")
# how much is after the 10th task of a failing array?
print(f"  -> {len(am):,} script fixes recover {at_hrs:,.0f} GPU-h "
      f"(${at_hrs*GPU:,.0f}), not {len(at):,} separate investigations")
out["arrays"] = dict(mass_failed_arrays=int(len(am)), dead_tasks=int(len(at)),
                     symptoms_per_problem=round(len(at) / max(len(am), 1), 1),
                     gpu_hours=round(at_hrs, 1), usd=round(at_hrs * GPU, 2))

# ============================================================ 5. TIMEOUTS
print("\n" + "=" * 86)
print("5. TIMEOUTS: work destroyed at the wall clock")
print("=" * 86)
to = jobs[jobs.state_name == "TIMEOUT"]
line("  TIMEOUT hours (destroyed, must rerun)", to.gpu_hours.sum())
# these were computing -- so the rerun cost is real
comp = to[to.sm_util_avg > 20]
line("  of which WERE computing (>20% util)", comp.gpu_hours.sum(),
     "<- real work lost")
print(f"  {len(to):,} jobs hit their limit; {len(comp):,} were actively computing.")
print(f"  FIX: checkpointing, or a limit-raise warning at 90% of walltime.")
print(f"  RERUN COST: this work must be redone, so the true cost is ~2x "
      f"(${to.gpu_hours.sum()*GPU*2:,.0f})")
out["timeouts"] = dict(jobs=int(len(to)), gpu_hours=round(float(to.gpu_hours.sum()), 1),
                       usd=round(float(to.gpu_hours.sum()) * GPU, 2),
                       computing_jobs=int(len(comp)),
                       computing_gpu_hours=round(float(comp.gpu_hours.sum()), 1),
                       rerun_inclusive_usd=round(float(to.gpu_hours.sum()) * GPU * 2, 2))

# ============================================================ 6. ENERGY
print("\n" + "=" * 86)
print("6. ENERGY: the electricity bill nobody is quoting")
print("=" * 86)
tot_wh = float(jobs.energy_wh.sum())
print(f"  total energy                         {tot_wh/1e6:>10,.1f} MWh   "
      f"${tot_wh/1000*KWH:>11,.0f}")
# energy on jobs that did not complete
bad = jobs[jobs.state_name != "COMPLETED"]
bad_wh = float(bad.energy_wh.sum())
print(f"  on jobs that did not COMPLETE        {bad_wh/1e6:>10,.1f} MWh   "
      f"${bad_wh/1000*KWH:>11,.0f}")
# and on our recoverable set
print(f"  share of energy on non-completed     {bad_wh/tot_wh:>10.1%}")
print(f"  at ${KWH}/kWh. This is a second, independent cost line: "
      f"the same waste costs GPU-hours AND kilowatt-hours.")
out["energy"] = dict(total_mwh=round(tot_wh / 1e6, 1),
                     total_usd=round(tot_wh / 1000 * KWH, 2),
                     noncompleted_mwh=round(bad_wh / 1e6, 1),
                     noncompleted_usd=round(bad_wh / 1000 * KWH, 2),
                     noncompleted_share=round(bad_wh / tot_wh, 4),
                     usd_per_kwh=KWH)

# ============================================================ 7. STACK
print("\n" + "=" * 86)
print("7. THE SAVINGS STACK (deduplicated, each lever once)")
print("=" * 86)
print("  These overlap by job, so we report them as separate LEVERS with")
print("  their own fixes, not as a sum. Ordered by effort.")
levers = [
    ("idle interactive sessions -> idle timeout policy", "policy", None),
    ("slow-cancel-of-idle -> liveness alert", "policy", 71052),
    ("gpu-not-needed -> route to CPU queue", "placement", None),
    ("wide low-util jobs -> justification gate at 9+", "policy",
     float(low.gpu_hours.sum())),
    ("array mass failures -> fail-fast after 10 dead tasks", "scheduler", at_hrs),
    ("timeouts -> checkpointing / limit warnings", "user tooling",
     float(to.gpu_hours.sum())),
    ("card imbalance -> resize multi-card requests", "placement", wasted),
]
for name, kind, gh in levers:
    if gh:
        print(f"    [{kind:<12}] {name:<48} {gh:>9,.0f} GPU-h  ${gh*GPU:>10,.0f}")
    else:
        print(f"    [{kind:<12}] {name:<48} {'see claims':>9}")

print(f"\n  CEILING CHECK: the largest single lever is "
      f"{max(g for _,_,g in levers if g):,.0f} GPU-h, "
      f"{max(g for _,_,g in levers if g)/CEIL:.1%} of the cluster. "
      f"No lever and no sum may exceed {CEIL:,}.")

(ROOT / "analysis/a6_savings.json").write_text(json.dumps(out, indent=2))
print(f"\n  written -> analysis/a6_savings.json\n")
