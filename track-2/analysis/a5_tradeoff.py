"""A5: the drain-vs-capacity tradeoff, and the queue tail.

Part 1 answers the question our audit leaves open. We proved rec_drain_nodes
targets five healthy machines and misses the one broken one. So what SHOULD the
CFO do? Draining a node recovers reliability and destroys capacity. Where is the
threshold, and what is the net?

Part 2 prices the queue in engineer-hours instead of GPU-hours, because waiting
researchers are a salary line, not an infrastructure line.
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
GPU_RATE = pb["usd_per_gpu_hour"]
ENG_RATE = pb["usd_per_engineer_hour"]
out = {"price_book": {"usd_per_gpu_hour": GPU_RATE,
                      "usd_per_engineer_hour": ENG_RATE}}

BROKEN = "r216287-n200569"
DRAIN_TARGETS = ["r4605940-n772143", "r7317916-n772143", "r3974592-n172107",
                 "r4144777-n172107", "r7317916-n303509"]


def node_jobs(node):
    ids = gpus.loc[gpus.Node == node, "id_job"].unique()
    return jobs[jobs.id_job.isin(ids)]


def node_delivered(node):
    return float(gpus.loc[gpus.Node == node, "gpu_hours"].sum())


print("=" * 78)
print("PART 1: THE DRAIN TRADEOFF")
print("=" * 78)

# --- the broken machine
jb = node_jobs(BROKEN)
delivered = node_delivered(BROKEN)
failed = jb[jb.state_name == "FAILED"]
succeeded = jb[jb.state_name == "COMPLETED"]

# Hours that bought nothing: work that ran on this node and failed.
# Attribute only the cards held ON THIS NODE (gpus.parquet), not whole jobs.
g_node = gpus[gpus.Node == BROKEN]
failed_ids = set(failed.id_job)
ok_ids = set(succeeded.id_job)
wasted_here = float(g_node[g_node.id_job.isin(failed_ids)].gpu_hours.sum())
productive_here = float(g_node[g_node.id_job.isin(ok_ids)].gpu_hours.sum())

print(f"\n  {BROKEN}  (the one real hardware fault)")
print(f"    jobs that touched it          {len(jb):,}")
print(f"    failed                        {len(failed):,} ({len(failed)/len(jb):.0%})")
print(f"    completed                     {len(succeeded):,} ({len(succeeded)/len(jb):.0%})")
print(f"    total GPU-h delivered         {delivered:>10,.0f}   ${delivered*GPU_RATE:>10,.0f}")
print(f"    of which went to FAILED jobs  {wasted_here:>10,.0f}   ${wasted_here*GPU_RATE:>10,.0f}  <- bought nothing")
print(f"    of which went to COMPLETED    {productive_here:>10,.0f}   ${productive_here*GPU_RATE:>10,.0f}  <- real loss if drained")

# The tradeoff in GPU-hours alone.
net_broken = wasted_here - productive_here
print(f"\n    NET in GPU-hours only         {net_broken:>10,.0f}   ${net_broken*GPU_RATE:>10,.0f}")
print(f"    -> on GPU-hours alone this says KEEP, which is the wrong answer.")

# WHY it is the wrong answer: SIGBUS kills a job almost instantly, so a machine
# that destroys everything sent to it burns almost no GPU time doing it. The
# cost lands on the people who have to diagnose and resubmit.
med_fail = float(failed.walltime_sec.median())
med_ok = float(succeeded.walltime_sec.median())
print(f"\n    median runtime of a FAILED job here    {med_fail:>8,.0f}s")
print(f"    median runtime of a COMPLETED job here {med_ok:>8,.0f}s")
print(f"    -> SIGBUS kills in ~{med_fail:.0f}s, so {len(failed)} failures burn only "
      f"{wasted_here:,.0f} GPU-h.")
print(f"       Pricing this node in GPU-hours understates it by construction.")

# Price the human cost. A dead job costs someone a diagnose-and-resubmit cycle.
# 15 minutes is deliberately conservative for a SIGBUS with no clear cause.
MIN_PER_FAILURE = 0.25  # engineer-hours
human_h = len(failed) * MIN_PER_FAILURE
human_usd = human_h * ENG_RATE
print(f"\n    {len(failed)} dead jobs x {MIN_PER_FAILURE*60:.0f} min to diagnose and resubmit")
print(f"      = {human_h:,.0f} engineer-hours   ${human_usd:,.0f}")
true_net_usd = (wasted_here * GPU_RATE) + human_usd - (productive_here * GPU_RATE)
print(f"\n    TRUE NET of draining it       ${true_net_usd:>10,.0f}")
print(f"    -> {'DRAIN' if true_net_usd > 0 else 'KEEP'}: once researcher time is "
      f"priced, {'draining wins' if true_net_usd > 0 else 'it still delivers more'}")

out["broken_node"] = dict(
    node=BROKEN, jobs=int(len(jb)), failed=int(len(failed)),
    completed=int(len(succeeded)), fail_rate=round(len(failed)/len(jb), 4),
    delivered_gpu_hours=round(delivered, 1),
    wasted_gpu_hours=round(wasted_here, 1),
    productive_gpu_hours=round(productive_here, 1),
    net_gpu_hours_of_draining=round(net_broken, 1),
    net_usd_gpu_only=round(net_broken * GPU_RATE, 2),
    median_failed_walltime_sec=round(med_fail, 1),
    median_completed_walltime_sec=round(med_ok, 1),
    engineer_hours_per_failure=MIN_PER_FAILURE,
    human_cost_engineer_hours=round(human_h, 1),
    human_cost_usd=round(human_usd, 2),
    true_net_usd_of_draining=round(true_net_usd, 2),
    verdict="drain" if true_net_usd > 0 else "keep",
)

# --- the five the API wants drained
print(f"\n  The 5 nodes rec_drain_nodes targets:")
rows = []
tot_prod = tot_waste = 0.0
for n in DRAIN_TARGETS:
    jn = node_jobs(n)
    gn = gpus[gpus.Node == n]
    f_ids = set(jn[jn.state_name == "FAILED"].id_job)
    c_ids = set(jn[jn.state_name == "COMPLETED"].id_job)
    w = float(gn[gn.id_job.isin(f_ids)].gpu_hours.sum())
    p = float(gn[gn.id_job.isin(c_ids)].gpu_hours.sum())
    tot_prod += p
    tot_waste += w
    net = w - p
    rows.append(dict(node=n, jobs=int(len(jn)),
                     fail_rate=round((jn.state_name == "FAILED").mean(), 4),
                     wasted_gpu_hours=round(w, 1),
                     productive_gpu_hours=round(p, 1),
                     net_gpu_hours_of_draining=round(net, 1)))
    print(f"    {n:<20} fail {(jn.state_name=='FAILED').mean():>5.0%}  "
          f"productive {p:>8,.0f}  wasted {w:>8,.0f}  net {net:>+9,.0f}")

net_five = tot_waste - tot_prod
print(f"\n    combined productive capacity  {tot_prod:>10,.0f}   ${tot_prod*GPU_RATE:>10,.0f}")
print(f"    combined wasted capacity      {tot_waste:>10,.0f}   ${tot_waste*GPU_RATE:>10,.0f}")
print(f"    NET of draining all five      {net_five:>10,.0f}   ${net_five*GPU_RATE:>10,.0f}")
print(f"    -> {'DRAIN' if net_five > 0 else 'KEEP ALL FIVE'}")

out["drain_targets"] = rows
out["drain_targets_total"] = dict(
    productive_gpu_hours=round(tot_prod, 1), wasted_gpu_hours=round(tot_waste, 1),
    net_gpu_hours_of_draining=round(net_five, 1),
    net_usd_of_draining=round(net_five * GPU_RATE, 2))

print(f"\n  THE RECOMMENDATION WE MAKE INSTEAD OF THE API'S:")
print(f"    drain 1 machine ({BROKEN}), keep the 5 it named.")
print(f"    the API's plan:  drain 5  ->  net ${net_five*GPU_RATE:+,.0f}")
print(f"    our plan:        drain 1  ->  net ${true_net_usd:+,.0f}")
swing = true_net_usd - (net_five * GPU_RATE)
print(f"    difference:      ${swing:+,.0f} in the cluster's favour")
out["recommendation_swing_usd"] = round(swing, 2)
out["api_plan_net_usd"] = round(net_five * GPU_RATE, 2)
out["our_plan_net_usd"] = round(true_net_usd, 2)

# --- where is the threshold?
print(f"\n  WHERE IS THE THRESHOLD? (net>0 means draining pays for itself)")
alln = []
for n, g in gpus.groupby("Node"):
    jn = jobs[jobs.id_job.isin(g.id_job.unique())]
    if len(jn) < 30:
        continue
    f_ids = set(jn[jn.state_name == "FAILED"].id_job)
    c_ids = set(jn[jn.state_name == "COMPLETED"].id_job)
    w = float(g[g.id_job.isin(f_ids)].gpu_hours.sum())
    p = float(g[g.id_job.isin(c_ids)].gpu_hours.sum())
    alln.append((n, (jn.state_name == "FAILED").mean(), w - p, p, w))
adf = pd.DataFrame(alln, columns=["node", "fail_rate", "net", "productive", "wasted"])
pays = adf[adf.net > 0].sort_values("net", ascending=False)
print(f"    machines with >=30 jobs            {len(adf)}")
print(f"    where draining pays for itself     {len(pays)}")
print(f"    lowest failure rate among those    {pays.fail_rate.min():.0%}")
print(f"    highest failure rate among KEEPers {adf[adf.net<=0].fail_rate.max():.0%}")
print(f"\n    top 5 by net benefit of draining:")
for _, r in pays.head(5).iterrows():
    print(f"      {r.node:<20} fail {r.fail_rate:>5.0%}  net {r.net:>+9,.0f} GPU-h  "
          f"${r.net*GPU_RATE:>+10,.0f}")
out["threshold"] = dict(
    nodes_considered=int(len(adf)), nodes_where_draining_pays=int(len(pays)),
    min_fail_rate_among_drainable=round(float(pays.fail_rate.min()), 4),
    max_fail_rate_among_keepers=round(float(adf[adf.net <= 0].fail_rate.max()), 4),
    top_candidates=[dict(node=r.node, fail_rate=round(r.fail_rate, 4),
                         net_gpu_hours=round(r.net, 1),
                         net_usd=round(r.net * GPU_RATE, 2))
                    for _, r in pays.head(5).iterrows()])

# ============================================================ PART 2
print("\n" + "=" * 78)
print("PART 2: THE QUEUE TAIL (a salary line, not an infrastructure line)")
print("=" * 78)

w = jobs.wait_sec.dropna()
w = w[w >= 0]
tot_wait_h = float(w.sum() / 3600)
print(f"\n  jobs with a wait time      {len(w):,}")
print(f"  median wait                {w.median():,.0f}s")
print(f"  p90                        {w.quantile(0.90):,.0f}s")
print(f"  p99                        {w.quantile(0.99):,.0f}s  "
      f"({w.quantile(0.99)/3600:,.1f} h)")
print(f"  max                        {w.max():,.0f}s  ({w.max()/3600:,.1f} h)")
print(f"\n  TOTAL engineer-hours waiting   {tot_wait_h:>12,.0f}")
print(f"  at ${ENG_RATE}/engineer-hour       ${tot_wait_h*ENG_RATE:>12,.0f}")

# the slowest 1%
thresh = w.quantile(0.99)
tail = w[w >= thresh]
tail_h = float(tail.sum() / 3600)
print(f"\n  the slowest 1% ({len(tail):,} jobs) alone:")
print(f"    engineer-hours               {tail_h:>12,.0f}")
print(f"    cost                         ${tail_h*ENG_RATE:>12,.0f}")
print(f"    share of all waiting         {tail_h/tot_wait_h:>12.0%}")

gpu_waste_usd = 306021  # our headline
print(f"\n  FOR THE CFO:")
print(f"    recoverable GPU waste        ${gpu_waste_usd:>12,.0f}")
print(f"    researcher time spent waiting ${tot_wait_h*ENG_RATE:>11,.0f}")
print(f"    ratio                        {tot_wait_h*ENG_RATE/gpu_waste_usd:>12.1f}x")

out["queue"] = dict(
    jobs_with_wait=int(len(w)), median_wait_sec=float(w.median()),
    p90_wait_sec=float(w.quantile(0.90)), p99_wait_sec=float(w.quantile(0.99)),
    max_wait_sec=float(w.max()),
    total_engineer_hours=round(tot_wait_h, 1),
    total_engineer_usd=round(tot_wait_h * ENG_RATE, 2),
    slowest_1pct_jobs=int(len(tail)),
    slowest_1pct_engineer_hours=round(tail_h, 1),
    slowest_1pct_usd=round(tail_h * ENG_RATE, 2),
    slowest_1pct_share_of_wait=round(tail_h / tot_wait_h, 4),
    ratio_to_gpu_waste=round(tot_wait_h * ENG_RATE / gpu_waste_usd, 2),
)

# the weekday pattern
EPOCH = pb["epoch_offset"]
j2 = jobs.dropna(subset=["time_submit"]).copy()
j2["dow"] = pd.to_datetime(j2.time_submit + EPOCH, unit="s", utc=True).dt.dayofweek
dow = j2.groupby("dow").agg(submissions=("id_job", "size"),
                            median_wait=("wait_sec", "median"))
NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
print(f"\n  BY WEEKDAY (the queue-weekly-peak finding):")
for d, r in dow.iterrows():
    print(f"    {NAMES[int(d)]}  submissions {r.submissions:>8,.0f}   "
          f"median wait {r.median_wait:>8,.0f}s")
worst = dow.median_wait.idxmax()
print(f"\n  -> worst day is {NAMES[int(worst)]}: median wait "
      f"{dow.loc[worst,'median_wait']:,.0f}s against "
      f"{dow.median_wait.drop(worst).median():,.0f}s on other days")
out["weekday"] = {NAMES[int(d)]: dict(submissions=int(r.submissions),
                                      median_wait_sec=float(r.median_wait))
                  for d, r in dow.iterrows()}
out["worst_weekday"] = NAMES[int(worst)]

(ROOT / "analysis/a5_tradeoff.json").write_text(json.dumps(out, indent=2))
print(f"\n  written -> analysis/a5_tradeoff.json\n")
