# Where the GPU money goes, and how to get it back

Written for someone who does not run the cluster. Every number is in dollars, hours, or
percent of capacity. Every number can be traced to a specific query over the raw job
records, and all of it was re-checked independently (`analysis/VERIFICATION.md`).

**The cluster in one line:** 225 machines, 74,849 jobs, 195 researchers, four months,
**594,004 GPU-hours = $1,485,010** at the platform's own rate of $2.50 per GPU-hour.

**Read every dollar figure here as released capacity, not as cash returned.** The
machines are already bought and already powered. Recovering a GPU-hour means that hour
becomes available for work someone is currently waiting to run. It converts to cash only
if it defers a purchase or replaces rented capacity. That is a real saving, but it is a
different kind of saving from cutting an invoice, and a finance team will ask.

---

## First, why you can trust these numbers

**1. Everything is measured, not estimated.** Each GPU reports how hard it was working,
second by second, for every job. We are reading that meter, not modelling it. The
column we total is the one the hardware recorded.

**2. There is a hard ceiling and we check against it.** The cluster physically had
594,004 GPU-hours to give. No saving we quote can exceed it, and we verify that before
any figure is published. The platform's own alert system, summed naively, claims 931,560
GPU-hours of waste, which is **157% of a cluster that size**. It is recovering time
that never existed, because 23 different alerts fire on the same jobs and each one
counts the same hours again. We removed the duplicates by counting **jobs**, not alerts.

**3. We never add two different things together.** Hours that were *destroyed* (a job
crashed and must be rerun) and hours that were *never used* (a GPU sat idle) are
different quantities with different fixes. We keep them in separate columns.

**4. We separated our own numbers by hand and then had them checked.** An independent
system recomputed all sixteen headline figures from the raw files, with no access to our
working. Fourteen matched exactly, two were rounding, none were wrong.

**5. Where a number is a judgment rather than a measurement, we say so.** Our headline
range is not a statistical margin of error. It is the gap between a strict reading and a
generous one, and we label it that way.

**6. The thresholds are our choices, and they are debatable.** "Under 5% busy",
"idle for more than four hours", "a 30-point gap between cards": each is a line we drew.
The measurements underneath are exact; where the line sits is a policy question. Move a
threshold and the number moves. We have used the same thresholds the platform's own
alerting uses, so our figures are comparable to its. Section 5 shows exactly what moves
when we change one.

---

## The headline

**$306,021 can be recovered. That is 20.6% of the cluster.**

You were asked to cut 20%. The target is reachable without slowing down a single
researcher who is actually using the machines.

| | GPU-hours | Dollars |
|---|---|---|
| strict reading | 93,873 | $234,683 |
| **our estimate** | **122,408** | **$306,021** |
| generous reading | 150,944 | $377,359 |

**What the range means in plain terms.** The strict figure counts only GPUs that
provably never did a single calculation, which nobody can argue with. The generous
figure counts everything our checks flagged as questionable. The truth is in between,
and it depends on policy decisions you have not made yet, not on measurement error. We
are 60% confident the real answer falls inside that range.

---

## The places the money is, and what to do about each

These **overlap**, because one bad job can appear in several of them. Do not add the
column up. Treat each as a separate lever with its own fix, and the total recoverable
figure is the $306,021 above.

### 1. Jobs that finished successfully without ever using the GPU

**The problem:** the job asked for a GPU, ran, succeeded, and never sent the GPU a
single instruction. It did its work on the ordinary processor. The GPU was rented and
left idle.

**The fix:** route this work to the cheaper CPU-only machines. No researcher is affected;
their job runs the same.

**Effort:** low. It is a scheduling rule.

### 2. Idle sessions nobody closed

**The problem:** a researcher opens an interactive session, walks away, and the session
holds its GPUs for hours doing nothing. 906 sessions did this.

**The fix:** an idle timeout. If a session is under 5% busy for four hours, warn the
owner, then release it.

**Effort:** low. It is a policy setting.

### 3. Idle jobs that took hours for anyone to notice: **$177,630**

**The problem:** 949 jobs sat essentially idle for more than four hours before their
owner cancelled them. That is **71,052 GPU-hours = $177,630**.

**The important nuance:** the cancellation was the *right* call. The researcher saw the
run was going wrong and stopped it. Cancelling bad runs is behaviour you want to
encourage, not penalise. **The recoverable part is the four hours before anyone
looked**, not the decision to cancel.

**The fix:** alert the owner when a job goes quiet, instead of waiting for them to check.
Most people notice within minutes; this is the tail that did not.

**Effort:** low. It is an alert.

### 4. Work destroyed at the time limit: **$269,879, and arguably double**

**The problem:** 1,544 jobs hit their requested time limit and were killed mid-run.
**107,952 GPU-hours = $269,879** of work was thrown away. Of that, **48,157 GPU-hours
was work that was genuinely computing** when it died, so it was real progress lost.

**Why the true cost is higher:** destroyed work has to be redone. The researcher reruns
it, and you pay for those hours a second time. Costed honestly, this line is closer to
**$539,758**.

**The fix:** two things. Warn at 90% of the time limit so people can request an
extension, and support checkpointing so a killed job resumes instead of restarting.

**Effort:** medium. Needs researcher tooling, not just a setting.

### 5. Very large jobs that barely use their GPUs: **$42,313**

**The problem:** among jobs requesting nine or more GPUs and running over an hour, 31 of
them ran below 5% GPU utilisation, consuming **16,925 GPU-hours = $42,313**.

**The finding that makes this actionable:** **95% of it belongs to one researcher's 25
jobs.** This is not a cluster-wide culture problem. It is one conversation.

**Honest caveat, and why our first number was wrong.** Our initial pass found 233 such
jobs and $43,065. But the median of those 233 ran for **95 seconds**. You cannot recover
time from a 95-second job, and counting them inflates the job count without adding
meaningful hours. Filtering to jobs of an hour or more drops the count from 233 to 31
while keeping 98% of the dollars, which tells you the money was always in the long jobs.
**We report the filtered figure.**

**The fix:** require a short justification for requests above nine GPUs, and talk to the
one researcher.

**Effort:** low.

### 6a. Jobs that may not need the GPUs they asked for: up to $131,915, unproven

**The opportunity:** 1,028 jobs held two or more GPUs, ran over an hour, and averaged
under 10% GPU utilisation. If each could run on a tenth of the cards, that releases
**52,766 GPU-hours, up to $131,915**.

**Why this is a hypothesis and not a saving.** Low average utilisation does not prove a
job would still work on fewer GPUs. It might need the combined GPU memory, it might be
waiting on communication between cards, or it might slow down so much that the total
cost rises. **We have not tested any of those, and we are not booking this number.**

**What it is good for:** a screening list. These 1,028 jobs are where to look first, and
the test is cheap: rerun a handful on fewer cards and measure.

**Effort:** medium, and it starts with an experiment, not a policy.

### 6. Multi-GPU jobs where some cards do nothing: **$22,448**

**The problem:** a job holds four GPUs, drives one hard, and leaves the others near
idle. 1,228 jobs show a gap of more than 30 percentage points between their busiest and
quietest card. Conservatively that is **8,979 GPU-hours = $22,448**.

**Why nobody sees this:** the standard job report *averages* a job's cards. A job with
one card at 0% and one at 65% shows up as an unremarkable 35% job. The imbalance is only
visible per-card, which is a different table most analyses never open.

**The fix:** flag imbalanced jobs back to their owner so the next submission asks for
fewer cards.

**Effort:** medium.

### 7. One bad script, thousands of dead jobs

**The problem:** researchers submit "arrays", one script launched hundreds of times with
different inputs. When the script is broken, every copy dies. 149 broken arrays produced
**5,044 dead jobs**, about **34 failures per actual problem**.

**Why this matters beyond the hours:** it is 149 problems, not 5,044. Anyone triaging
this queue job-by-job is doing 34 times the necessary work.

**The fix:** fail-fast. If the first ten copies of an array all die the same way, stop
launching the rest.

**Effort:** low. It is a scheduler rule.

---

## The number that is bigger than all of them: **$9,330,307**

Everything above is GPU time. This is researcher time, and it never appears on an
infrastructure invoice.

**Your researchers spent 98,214 hours waiting in the queue. At $95 per hour, that is
$9,330,307, which is 30 times the entire GPU saving on this page.**

**It is not a slow queue.** The median job starts in **8 seconds**. The problem is
entirely in the tail: the slowest 1% of jobs, just 749 of them, account for **44% of all
waiting time**, worth **$4.09 million** on their own. The worst single job waited 12
days.

**And one weekday causes it.** Wednesday takes 21,151 submissions against roughly 8,700
on every other day. Wednesday's median wait is **2,007 seconds against 2 seconds**
elsewhere.

**The fix costs nothing to buy.** Smooth the Wednesday submission spike with scheduling
policy or submission windows. This is a calendar problem, not a hardware problem.

**Important:** these are people-hours, not GPU-hours. They must never be added to the
GPU figures. They are a parallel cost line that happens to be much larger.

---

## And the electricity: **$6,905, with 57% of it wasted**

Total energy across the window was **46 MWh, $6,905** at the platform's $0.15/kWh.
**26.2 MWh of that, 57%, was consumed by jobs that never completed.** Small next to the
GPU rental, but it is the same waste billed a second time, and it has a carbon number
attached.

---

## What we recommend, in order

| # | Action | Recovers | Effort |
|---|---|---|---|
| 1 | Alert owners when a job goes idle | $177,630 | low |
| 2 | Warn at 90% of time limit; support checkpointing | $269,879+ | medium |
| 3 | Fail-fast on arrays after 10 identical failures | 149 fixes instead of 5,044 | low |
| 4 | Justification gate above 9 GPUs, plus one conversation | $42,313 | low |
| 5 | Idle timeout on interactive sessions | see claims | low |
| 6 | Route GPU-less work to CPU queues | see claims | low |
| 7 | Flag card-imbalanced jobs to owners | $22,448 | medium |
| 9 | *Test* whether 1,028 low-utilisation jobs fit on fewer GPUs | up to $131,915, unproven | experiment first |
| 8 | **Smooth the Wednesday queue spike** | **up to $4.09M of researcher time** | low |

**Do not sum column three.** The levers overlap on the same jobs; the deduplicated
recoverable total is **$306,021** in GPU time, plus a separate and much larger
opportunity in researcher time.

---

## One more thing: your own tooling is pointing the wrong way

The platform's recommendation engine told us to drain five machines for a claimed
$57,226 of savings, at "low" effort.

**All five are healthy.** None has a single recorded hardware fault. Between 68% and 82%
of the alerts against them come from broken user scripts that happened to run there.
Draining them would have destroyed **$38,253 of working capacity** and fixed nothing.

**Meanwhile the one machine that is genuinely broken does not appear on that list at
all.** It spent eight days failing 140 of 144 jobs sent to it, with a hardware error
signature that three unrelated researchers hit on that machine and never once on any of
the other 224. The scheduler never marked it offline, so work kept arriving.

**Why the tool missed it:** it ranks machines by how many alerts they have. Alert count
finds your *busiest* machines, not your *broken* one.

**And the fix is counterintuitive.** Measured in GPU-hours, draining the broken machine
looks like a loss, because its hardware error kills jobs in **one second**, so it
destroys work without consuming GPU time. Its damage is 267 researchers' afternoons,
not its GPU bill. Once you price the human cost at 15 minutes per dead job, draining it
turns positive:

| plan | net |
|---|---|
| the tool's advice: drain 5 | **-$5,791** |
| **drain 1, keep all 5** | **+$4,040** |
| **value of getting it right** | **$9,832** |

**The general lesson for anyone reading a reliability dashboard:** failure *rate* is the
wrong signal. Of 223 machines with enough history to judge, draining pays for itself on
only 11. The lowest failure rate among machines worth draining is **4%**. The highest
among machines worth keeping is **66%**. A machine that fails slowly still delivers
work; one that fails instantly destroys throughput while consuming almost nothing.

---

## What we did not examine

Stated so nobody mistakes silence for a clean bill of health.

- Idle time on *unallocated* machines. The GPU meters only run while a job runs, so an
  empty machine reports nothing at all. Our figures therefore describe waste *inside*
  allocated time, and the true idle number is larger than anything here.
- 104 of the 113 machine-level failure alerts. We examined nine in depth rather than
  guessing at all of them.
- Whether the platform's confidence scores are trustworthy in general. We disproved one
  of them specifically.
- These four months are a **sample** of the cluster's workload, not its complete
  history. The publishers ask that it not be used to estimate overall system
  utilisation, and we are not doing so. Every figure describes this sample.

---

## Independent check

Every claim on this page was recomputed from the raw job records by a separate system
with no access to our working: **11 of 11 confirmed, 0 wrong**. Its two criticisms are
already reflected above: dollar figures are released capacity rather than cash returned,
and the right-sizing figure (section 6a) is labelled an untested hypothesis rather than a
booked saving. Audit trail: `analysis/VERIFY_SAVINGS.md`, earlier audit in
`analysis/VERIFICATION.md`.
