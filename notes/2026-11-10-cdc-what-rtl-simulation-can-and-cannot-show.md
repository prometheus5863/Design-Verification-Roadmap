# CDC verification basics — and the sharp line between what RTL simulation can and cannot show

**Date:** 2026-11-10
**Phase 6 item started:** *CDC verification basics* (previously unstarted)
**Worked example:** `examples/phase6_cdc_basics/`

## 0. Sourcing, stated up front

The **measured** content of this note — every number in §4 — comes from
`examples/phase6_cdc_basics/`, run today, transcripts committed. The
**conceptual** content of §1–§3 and §6 is established digital-design
knowledge rather than a fresh literature fetch, and no live search was
performed for it. The canonical references I am working from, named so a
future session can verify rather than trust:

- **C. E. Cummings, "Clock Domain Crossing (CDC) Design & Verification
  Techniques Using SystemVerilog", SNUG 2008** — the standard treatment of
  the crossing taxonomy and of why multi-bit crossings need either Gray
  coding or a handshake.
- **C. E. Cummings, "Simulation and Synthesis Techniques for Asynchronous
  FIFO Design", SNUG 2002** — the async-FIFO Gray-pointer construction.

Neither was fetched. They are cited as *where to check this*, not as
evidence I examined today. That distinction is the one this repository has
spent two months learning to keep.

## 1. The two failure mechanisms, which are genuinely different

Almost every CDC discussion blurs these together. They have different
causes, different fixes, and — crucially for a verification engineer —
**different observability in simulation.**

### 1a. Metastability (a single bit, a timing problem)

A destination flop samples a source signal that is changing within its
setup/hold window. The output can hang between levels for an unbounded
time before resolving to 0 or 1. This is a continuous-time, analogue
phenomenon.

The fix is a **two-flop synchroniser**: give the first flop's possibly
metastable output a full destination clock period to resolve before the
second flop samples it. Depth is a reliability choice, quantified by mean
time between failures, whose standard form is

    MTBF = exp(t_r / tau) / (T_w * f_dst * f_src_transitions)

with `t_r` the resolution time allowed (≈ one destination period per extra
flop), `tau` the flop's resolution time constant, and `T_w` its sampling
aperture. The shape is what matters: **MTBF grows exponentially in the
time you allow and only linearly in the clock rates.** That is why two
flops is usually enough and a third is cheap insurance at very high
frequency, and why "add more synchroniser stages" is a reliability dial,
not a correctness fix.

**What this costs you:** exactly two destination clock edges of latency,
and the destination sees a value that is 2 edges stale. Checked exactly as
`L1` in the example — a 2FF synchroniser whose measured latency is
anything other than 2 is not a 2FF synchroniser.

### 1b. Incoherency (several bits, a logical problem)

A multi-bit value crosses, and the destination samples a combination of
bits that the source **never simultaneously held**. Each bit may resolve
perfectly — no metastability survives the synchronisers — and the result
is still garbage, because the bits resolved against *different* source
values.

Per-bit 2FF synchronisers do **not** fix this. They fix 1a and are silent
about 1b. This is the single most common CDC misconception, and it is why
`cdc_sync_2ff` in the example is width-parameterised: the bench has to
instantiate the wrong thing to show that it is wrong.

The two fixes:

- **Gray coding**, when the value is a counter: successive codes differ in
  exactly one bit, so whatever the per-bit skew, the destination samples
  either the old code or the new one — never a third. This is why async
  FIFO pointers are Gray-coded.
- **A handshake / data-ready flag**, for arbitrary data: hold the data
  stable, cross a single-bit "valid" through a synchroniser, and let the
  destination capture the (already stable) bus once valid arrives. The
  single bit is the only thing crossing, so 1b never arises.

### 1c. The third one people forget: pulse loss

A pulse one source-clock wide, crossed into a **slower** domain, is simply
missed when no destination edge falls inside it. Nothing is metastable and
nothing is incoherent; the event is just gone. The fix is to convert the
pulse into a **level toggle** at the source — a signal that never returns
to its previous value, so it cannot be missed, only delayed — and convert
each edge back to a pulse at the destination. Valid only if source events
are spaced by more than the synchroniser latency; otherwise you need a
full handshake with acknowledge.

## 2. THE OBSERVABILITY POINT, which is the real content of today's work

> **A zero-delay RTL simulation cannot show the incoherency bug (1b), and
> no simulation of any kind represents metastability (1a).**

For 1b: in the simulation, every bit of a vector changes at the same
instant. The destination flops therefore sample a coherent snapshot —
every cycle, forever. The broken crossing is **green**. Measured today:
**0 incoherent samples out of 417** on a textbook-broken 8-bit crossing.

For 1a: metastability is a continuous-time behaviour of a physical flop.
An event-driven simulator has two-valued (or four-valued) logic and
discrete time. It has no representation of "between levels for an
unbounded time". You can *model* its consequence — a synchroniser model
that randomly delays or inverts its output — but a plain RTL simulation
shows nothing.

So the practical conclusion, which is also the interview answer:

**CDC is a structural property of the netlist, and it belongs to a static
CDC checker, not to simulation.** The tool enumerates every signal
crossing a clock boundary and classifies it: is it synchronised, is it a
multi-bit crossing without a handshake, is a synchronised signal being
combined with an unsynchronised one, is there reconvergence of separately
synchronised bits. These are questions about *structure*, answerable
without stimulus — which is exactly why they are answerable at all.
Simulation's remaining jobs are (i) functional verification of the
handshake protocol you built, and (ii) with a metastability-injection
model, showing the design tolerates the resolution delay.

A green simulation of a multi-bit crossing is evidence of almost nothing,
and that sentence is the thing worth remembering from today.

## 3. The skew model, and why it is in the testbench

To make 1b visible, the example models the one physical fact the
zero-delay simulation discards: **the bits do not arrive at the
destination flops at the same moment.** `SKEW_UNIT_NS` delays bit *i* of
the crossing by *i* ns.

Three things about this, all deliberate:

1. **It lives in the testbench, not the RTL.** It is a model of reality,
   not design intent. Nothing in `cdc_crossings.v` is unsynthesisable.
2. **1 ns/bit is mild, not contrived.** The source clock period is 10 ns,
   so the vector is fully settled long before the next source edge. This
   is an ordinary amount of skew, not a pathological one.
3. **It is a macro, not a parameter, because of a defect** — see §5(a).

The model is honest about its own limits: it demonstrates 1b and says
nothing about 1a. The mutation test then found a defect that is *purely*
1a, and the bench could not see it — §5(d).

## 4. Measured

| quantity | zero-delay | 1 ns/bit skew |
|---|---|---|
| destination samples | 417 | 417 |
| **incoherent, binary crossing (broken)** | **0** | **28** |
| **incoherent, Gray crossing (correct)** | **0** | **0** |
| source pulses generated | 85 | 85 |
| pulses seen, naive crossing | 25 (**60 lost**) | 25 |
| pulses seen, toggle handshake | **85 (exact)** | **85 (exact)** |
| 2FF latency, destination edges | **2 (exact)** | 2 |
| checks | 8 passed, 0 failed | 9 passed, 0 failed |

First incoherency at *t* = 425 ns: previous sample 20, sampled **16** — a
value the counter did not hold between those two samples.

Three things are worth reading off this table rather than the prose:

- The **binary row** is the finding: the same broken design reads 0 and 28
  depending only on whether the simulation models bit skew.
- The **Gray row** is the control. If Gray were also 28 under skew, the
  skew model would be indicting the synchroniser rather than the encoding.
  It is 0, and that is what makes the comparison mean something.
- The **naive pulse row** loses 71 % of events with no skew model at all,
  because pulse loss (1c) is a *sampling-rate* problem, not a *skew*
  problem, and is therefore the one CDC failure mode that plain simulation
  **does** show. Worth knowing which of the three you can catch for free.

## 5. Four defects found while building this, all in my own work

**(a) `-PSKEW_UNIT=1` silently did nothing.** Icarus's `-P` requires a
hierarchical path (`-Ptb.SKEW_UNIT=1`), so the "skewed" run was a second
zero-skew run. It reported `ALL_PASS` and was indistinguishable from a
successful skew run **except that the B2/B3 checks were quietly absent
from the output.** A silent no-op on the one knob the whole example turns
is the worst available failure mode. Now a macro — a typo is a compile
error — plus check `K1`, which proves which mode elaborated by witnessing
whether the skewed copy ever differs from its source (0 vs 2828 times),
and three cross-mode checks in the runner that would each have fired.

**The general lesson:** a knob that can fail silently needs a check that
observes its *effect*, not its *setting*. `K1` does not read `SKEW_UNIT`
and trust it; it watches the wires.

**(b) The exact pulse-count check failed at 86 of 87 — and the handshake
was fine.** The bench compared a source-domain counter against a
destination-domain counter with a pulse still in flight. The end-of-test
condition was ill-defined, which is a classic cross-domain testbench bug
and precisely the sort of thing that gets "fixed" by relaxing the check to
`>= gen_count - 1`. Fixed properly: quiesce the source, then drain, so the
equality holds **by construction** rather than by luck with where the
simulation ended.

**(c) A truncation that inverted a reported result.** The detail strings
were held in `reg [1023:0]` — 128 characters — and were silently truncated
**from the left**, so `"incoherent binary samples = 0"` printed as
`"coherent binary samples = 0"`. The report said the opposite of the
measurement. Verilog string-to-vector assignment truncates the high bits,
i.e. the *start* of the string, which makes this failure mode especially
nasty: the tail that survives still reads as a sentence.

**(d) The mutation test's survivor is the thesis restated.** `C7` compares
a synchronised signal against the unsynchronised source — a real and
serious CDC defect, since it puts a metastable node directly into
destination combinational logic. **The bench cannot see it.** The bench
measures functional coherency and pulse accounting; this defect is
neither. It changes *which flop can go metastable*, which is §2's 1a, and
no simulation here represents that at all. So the survivor is not a hole
to patch — it is §2's argument arriving from a second direction, made by a
defect instead of by assertion. It is pinned as an **expected** survivor
with that reason recorded, two-sidedly: a new survivor fails the run, and
so does this one suddenly being *detected*.

## 6. Interview-prep pass on this topic

Short answers, since the Phase 6 interview-prep item is still open and
this is the first topic ready for it.

**Q. Why two flops?** The first absorbs the metastability; the second
samples it after a full destination period, by which time it has resolved
with overwhelming probability. Depth trades latency for MTBF, which grows
exponentially in the resolution time allowed.

**Q. Can I use per-bit 2FF synchronisers on a bus?** No. They fix
metastability per bit and do nothing about coherency: the destination can
latch a combination the source never held. Gray-code it (if it is a
counter) or cross a single valid bit and hold the bus stable.

**Q. Why are async FIFO pointers Gray-coded?** Only one bit changes per
increment, so any sampling skew yields the old pointer or the new one —
never a spurious third value. A wrong-but-adjacent pointer makes the FIFO
look momentarily emptier or fuller than it is, which is conservative and
safe; a spurious value is not.

**Q. How do you cross a single-cycle pulse into a slower domain?**
Toggle a level at the source, synchronise the level, edge-detect at the
destination. If events can arrive faster than the synchroniser latency,
you need a full request/acknowledge handshake instead.

**Q. Why can't you just simulate CDC?** Because the two mechanisms are
invisible to it: incoherency requires modelling per-bit arrival skew that
a zero-delay simulation discards, and metastability has no representation
in discrete-time two-valued logic at all. CDC is a structural property and
belongs to a static checker. *(And I can now point at a measurement: 0
incoherent samples out of 417 on a crossing that breaks 28 times once the
skew is modelled.)*

**Q. What does a static CDC tool actually report?** Unsynchronised
crossings; multi-bit crossings without a handshake; synchronised signals
recombined with unsynchronised ones; reconvergence of separately
synchronised bits; and reset-domain crossings. All answerable from
structure, without stimulus.

**Q. Reset CDC?** An asynchronous reset asserted in one domain and
released asynchronously with respect to another domain's clock has the
same removal-timing problem as any other async signal. The standard
answer is the asynchronous-assert / synchronous-de-assert reset
synchroniser. **Not demonstrated in today's example** — it is a timing
property and the same §2 argument applies, so faking a simulation of it
would have been worse than leaving it out. On the standing list.

## 7. What is NOT covered, recorded so it is not mistaken for done

- **Reset-domain crossing**, per §6's last answer: discussed, not built.
- **Async FIFO**, the natural next example: the Gray pointer here is the
  ingredient, but no FIFO is built, so full/empty generation and the
  pointer-comparison trick are untouched.
- **A metastability-injection synchroniser model**, which is the only way
  simulation can say anything about 1a. This is the one piece that would
  let the bench see mutant `C7`, and it is therefore the highest-value
  next step for the suite rather than for the RTL.
- **A structural CDC checker.** §2 argues that this is where CDC belongs,
  and the repository does not have one. Writing even a crude one — parse
  the RTL, find signals assigned in one clock domain and read in another,
  classify — would be a real Phase 6 artefact and would catch `C7` in one
  pass. The argument for it is now made by a measurement rather than by
  assertion, which is the strongest form this repository's standing list
  has ever been able to give an item.
