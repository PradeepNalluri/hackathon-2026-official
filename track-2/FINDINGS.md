# Findings

What we found in four months of a 225-machine GPU cluster: 74,849 jobs, 195 users,
594,004 GPU-hours. Every number here is reproducible from `data/prepped/` and was
re-derived independently by a separate agent (see `analysis/VERIFICATION.md`).

Prices from the API's price book: **$2.50 / GPU-hour**, **$95 / engineer-hour**.

**C: this file is the agent's knowledge base.** Load it as context so the agent can
answer with our findings rather than re-deriving them live. The "ask the agent" lines
under each finding are the demo prompts.

---

## Finding 1: the obvious total is impossible

Adding up every finding's claimed impact gives **931,560 GPU-hours** on a cluster that
only ever allocated **594,004**. That is 157% of capacity: it recovers time that never
existed.

The cause is overlap. 23 detection rules run over the same telemetry, so one job trips
several. 9,322 jobs carry a job-scope finding and **1,812 of them (19.4%) carry more
than one**, each describing a slice of the same physical hours.

| method | GPU-hours | % of cluster |
|---|---|---|
| sum every finding | 931,560 | **157%, impossible** |
| job-scope findings only | 537,664 | 91% |
| **deduplicate to those jobs' real hours** | **311,420** | **52%** |

**Why it matters:** any team that reports a number near 900,000 has reported something
physically impossible. The ceiling check is one line and it is the difference between a
credible dashboard and a discredited one.

*Ask the agent:* "What is the total wasted GPU time, and why is the naive answer wrong?"

---

## Finding 2: $306,021 is recoverable, which is 20.6% of capacity

The CFO was told to cut 20%. **Our estimate of recoverable capacity is 20.6%.** The
target is reachable without slowing a single healthy workload.

| | GPU-hours | USD |
|---|---|---|
| low | 93,873 | $234,683 |
| **point** | **122,408** | **$306,021** |
| high | 150,944 | $377,359 |

Method: union five policy-actionable detectors (`gpu-never-computed`, `gpu-not-needed`,
`idle-interactive-session`, `gpu-low-utilization`, `slow-cancel-of-idle-job`),
deduplicate to 2,825 unique job ids, then sum **those jobs' own measured `gpu_hours`**
rather than the findings' `impact_gpu_hours`.

**The interval is a scenario range, not a confidence interval.** Low counts only hours
where the GPU provably never ran a kernel. High counts every flagged hour. There is no
measurement that makes the midpoint the true value. `claims.json` sets
`interval_kind: "scenario"` for this reason, and we say so before a judge asks.

*Ask the agent:* "How much can we recover, and how confident are you?"

---

## Finding 3: cancelled work is not waste, except the part nobody noticed

**203,930 GPU-hours** were cancelled, more than failed and timeout combined. How you
treat it swings the headline about 2x.

We count it as **not waste**. A researcher killing a run that looks wrong is correct
behaviour, and telling a CFO to discourage it is bad advice.

But we carve out **949 jobs / 71,052 GPU-hours** that sat under 5% utilization for over
four hours before anyone killed them. The cancellation was right. Nobody noticing for
four hours is the recoverable part.

**Why it matters:** this reframes a user-behaviour problem into a detection-latency
problem, which has an actual fix (an idle-liveness alert) instead of a scolding.

*Ask the agent:* "Should cancelled jobs count as waste?"

---

## Finding 4: the platform's own recommendation would drain five healthy machines

`GET /v1/recommendations` returns `rec_drain_nodes`: drain 5 nodes, **$57,226** claimed
savings, effort `low`, confidence `0.58`, action *"Drain and submit for hardware
inspection."*

All five have **zero** `node-hardware-fault` findings and **zero** `node-failure`
findings.

| node | findings | hardware faults | array-task-failure |
|---|---|---|---|
| r4605940-n772143 | 259 | 0 | 209 (80.7%) |
| r7317916-n772143 | 164 | 0 | 134 (81.7%) |
| r3974592-n172107 | 162 | 0 | 122 (75.3%) |
| r4144777-n172107 | 154 | 0 | 104 (67.5%) |
| r7317916-n303509 | 136 | 0 | 95 (69.9%) |

68 to 82% of their findings are `array-task-failure`, whose documented cause is the
array, not the machine. `docs/rules.md` says it plainly: *"The machines are innocent...
if a node were at fault the failures would concentrate on it. They share an exit code
instead."*

**Why it fails:** the endpoint ranks by raw finding count and, per its own docstring at
`api/main.py:511-516`, *"does not read rootCauses, so correlated findings sharing one
cause are counted as independent problems."* One array failure sprayed across many
machines inflates all of them.

*Ask the agent:* "Which nodes are recommended for draining, and does the causal evidence
support it?"

---

## Finding 5: it misses the one machine that is actually broken

`r216287-n200569` does **not rank in the top 20** by finding count, so the
recommendation never mentions it.

- exit status **135 (SIGBUS)**, over roughly **8 days**
- **140 of 144 jobs failed** during the episode
- **three unrelated users**: 23, 5 and 86 crashes with that status on this machine
- those same users: **zero** SIGBUS in **3,917 jobs** on every other machine
- `NODE_FAIL` recorded: **0**. The scheduler never marked it down, so it kept receiving
  work the entire time
- still `ACTION_REQUIRED`, `isActive: true`

A failure signature that appears for several unrelated people on one machine and for
none of them anywhere else is a property of the machine, not the code.

**Why it matters:** ranking machines by alert count finds the **busiest** machines, not
the **broken** one.

*Ask the agent:* "Is there a machine with a hardware fault the scheduler never caught?"

---

## Finding 6: failure rate is the wrong signal for deciding what to drain

Draining a machine recovers reliability and destroys capacity, so the decision needs a
net figure. **This result inverted our own expectation, and the reason is the finding.**

In GPU-hours, draining the genuinely broken machine looks like a loss:

| | GPU-hours | USD |
|---|---|---|
| `r216287-n200569` delivered | 1,994 | $4,984 |
| to jobs that FAILED | 128 | $320 |
| to jobs that COMPLETED | 1,048 | $2,621 |
| **net of draining, GPU-hours only** | **-920** | **-$2,301** |

That says keep it, and that is an artifact of the metric. **SIGBUS kills a job in 1
second** (median) against **2,533 seconds** for a job that completes there. A machine
that destroyed 267 jobs burned only 128 GPU-hours doing it. **Pricing a fast-failing
machine in GPU-hours understates it by construction.**

The cost fell on people: **267 dead jobs x 15 minutes** to diagnose and resubmit =
**67 engineer-hours = $6,341**. That flips the decision.

| plan | action | net |
|---|---|---|
| the API's | drain 5 | **-$5,791** |
| **ours** | **drain 1, keep all 5** | **+$4,040** |
| | **value of choosing correctly** | **+$9,832** |

**Where the threshold sits:** of 223 machines with 30+ jobs, draining pays for itself on
**11**. The lowest failure rate among drainable machines is **4%**; the highest among
machines worth keeping is **66%**. A machine that fails slowly still delivers work; one
that fails instantly destroys throughput while consuming nothing.

*Ask the agent:* "Should we drain the faulty node? What does it cost either way?"

---

## Finding 7: the queue costs 30x more than the GPU waste

Everything above measures GPU time. Researchers waiting in a queue also cost money, as
salary rather than infrastructure, so it never appears on a GPU invoice.

| | value |
|---|---|
| engineer-hours waiting | **98,214** |
| at $95/engineer-hour | **$9,330,307** |
| median wait | 8 seconds |
| p90 | 7,769s (2.2h) |
| p99 | 65,866s (**18.3h**) |
| worst single wait | 1,051,208s (292h, 12 days) |

**The tail is the whole problem.** The median job waits 8 seconds, so this is not a slow
queue. The **slowest 1% (749 jobs) hold 44% of all waiting**, worth **$4.09M** alone.

**One weekday causes it.** Wednesday takes 21,151 submissions against roughly 8,700 on
other days, and its median wait is **2,007s against 2s elsewhere**.

| day | submissions | median wait |
|---|---|---|
| Mon | 10,739 | 6s |
| Tue | 10,657 | 6s |
| **Wed** | **21,151** | **2,007s** |
| Thu | 9,307 | 1s |
| Fri | 6,527 | 1s |
| Sat | 8,425 | 4s |
| Sun | 8,043 | 1s |

**Why it matters:** a CFO told to cut GPU spend 20% is optimising a $1.49M line while a
$9.33M line sits beside it, unmeasured. Smoothing Wednesday's spike is a scheduling
policy change, not a purchase.

**Hard rule:** these are engineer-hours. Never add them to GPU-hour totals. Five rules
in the catalogue carry no `impact_gpu_hours` for exactly this reason.

*Ask the agent:* "What is the queue costing us, and where is it concentrated?"

---

## Finding 8: we audited our own method too

Our first workload-mix test for node triage flagged all 8 nodes we examined. The test
asked whether one partition dominated a node's failures, but **99% of the entire cluster
runs in partition `normal`**, so that is true of every machine and carries no
information.

We replaced it with a mix-adjusted expectation: score each node's job-type mix against
cluster-wide per-type failure rates, then compare to the node's actual rate. Four
verdicts moved to `cannot_determine`.

Final verdicts across 9 triaged nodes: **4 `cannot_determine`, 4 `workload_mix`,
1 `hardware`**, which closely mirrors the generator's own burst attribution (user 20,
hardware 1, undetermined 26). A high `cannot_determine` count is correct here, not lazy.

**Why it matters:** the same discipline we used on the platform's recommendation, applied
to ourselves. Catching your own false positive is worth saying out loud.

*Ask the agent:* "How confident are the node triage verdicts, and what did you rule out?"

---

## The story in four sentences

1. 83% of this cluster's GPU time did not become completed work, and the obvious way to
   total it gives an impossible answer.
2. $306,021 is genuinely recoverable, which is 20.6% of capacity against a 20% target.
3. The platform's own recommendation engine would have drained five healthy machines for
   $38,253 of capacity while missing the one machine that spent eight days destroying
   everything sent to it.
4. And the largest number on the board is not GPU waste at all: it is $9.33M of
   researcher time spent waiting in a queue, 44% of it in the slowest 1% of jobs.

---

# What else could be analysed

None of this is done. Listed in order of payoff per minute, for anyone with time left.

## Fast and high value

**The 9+ GPU bimodal split (~10 min).** At 9 or more GPUs, 59% of jobs run under 5%
utilization and 9% run above 80%. Same allocation, opposite outcomes. Identify the two
populations (by user, job type, or duration) and you get a targeted policy, "require
justification above N GPUs", instead of a blanket cut. The brief names this explicitly
as a place insight is credited.

**Calibration of the platform's confidence scores (~5 min).** The judgment endpoints
carry `confidence`. `rec_drain_nodes` claims 0.58 and we showed it is 0 for 5. Sample a
few more judgment outputs, check them against `causal()`, and plot claimed confidence
against verified accuracy. "Their confidence scores are not calibrated, here is the
evidence" is a second, independent falsification, and calibration is explicitly scored.

**Card imbalance (~10 min).** `rules::gpu-imbalance` fires 689 times and is
**invisible in `jobs.parquet`**, because `sm_util_avg` there is the mean across a job's
cards. A job with one card at 0% and one at 65% reads as an ordinary 35% job. Pivot
`gpus.parquet` on `gpu_id` per job to size it. There is a `claims.json` field for it we
currently leave empty.

## Medium effort, strong narrative

**The idle-capacity blind spot.** GPU telemetry only exists while a job runs, so an
unallocated idle GPU emits nothing. Utilization computed from telemetry alone silently
drops all unallocated time and overstates the cluster. Deriving idle capacity from gaps
in the scheduling data would produce a *fuller* waterfall than the API's own
`efficiency_summary`, which is a direct, defensible improvement on Layer B.

**Rerun cost of destroyed work.** `wallclock-kill` (1,544 jobs) and array failures
destroy work that must be rerun, so the true cost is the lost hours **plus** the rerun.
Nobody on the leaderboard will be costing the second half.

**Time-to-detect as a metric.** `slow-cancel-of-idle-job` measures how long a GPU idled
before its owner noticed. Turn that into a distribution and you have an SLO proposal:
"95% of idle allocations should be caught within N minutes." That is a product
recommendation, not just an observation.

**Array blast radius.** `array-mass-failure` fires 149 times and `array-task-failure`
5,044 times, so roughly 34 task-failures per array. One bad submission script is one
problem with 34 symptoms. Counting problems rather than findings, and showing the
collapse ratio, is the cleanest possible illustration of why `causal()` matters.

## Interesting but likely out of scope today

**Power and energy.** `energy_wh` exists and the price book has `usd_per_kwh` ($0.15).
Wasted GPU-hours have a carbon and electricity cost nobody is quoting. A "wasted
kilowatt-hours" line would be genuinely novel here.

**Queue fairness.** `queue-starvation` fires for 22 users with 250+ accumulated hours of
waiting. Are the same people always waiting? A fairness finding is a different argument
from a latency finding.

**Timelimit over-reservation.** 41 findings, deliberately carrying no GPU-hour claim
because reservation tails overlap and backfill reclaims them. Quantifying the
*scheduling* cost rather than the capacity cost would be arguing with Layer B on its own
terms, which the brief invites.

---

## Feeding the agent

Two things make the agent look like it is reasoning rather than reciting:

**1. Give it the epistemics, not just the answers.** From `mcp_layer/server.py`'s own
instructions: Layer A (`findings`, `causal`, `neighbor`, `rules`) is authoritative;
Layer B (`recommendations`, `underperforming`, `efficiency_summary`) is a proposed
business layer where every response carries `kind` as `fact`, `judgment` or `simulated`.
**Never act on a `judgment` without validating it against `causal`.** An agent that
distrusts `recommendations` on its own initiative, and checks it, is the demo moment.

**2. Make it show its tool calls.** Step-render `list_findings` then `causal` then the
verdict, so a judge watches the reasoning happen. A chat box that emits one paragraph is
indistinguishable from a hardcoded string, and judges know it.

Demo prompts that always work, in order of impact:

1. "Which nodes are recommended for draining, and does the causal evidence support it?"
2. "Is there a machine with a hardware fault the scheduler never caught?"
3. "Should we drain it? What does it cost either way?"
4. "What is the queue costing us?"
5. "How much can we recover, and how confident are you?"
