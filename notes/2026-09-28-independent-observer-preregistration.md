# Pre-registration — an observer with its own timebase (2026-09-28)

Written and committed **before** the code exists, continuing the practice this
repository has kept every session since 2026-09-21. Five questions Q1–Q5, five
checks V1–V5, scored verbatim in `AUTOMATION_LOG.md` whether they pass or fail.

## The item

2026-09-27 left this as the clear top item:

> **An INDEPENDENT observer for the serial line.** `UartSerialMonitor` decodes
> `rx` on the DUT's clock with the DUT's own algorithm, so under a baud
> mismatch it drifts WITH the DUT: 182 probes across ±7% of eps produced only 5
> disagreements in 1274 checks, and 4 of the 5 were the monitor flagging a
> framing error the DUT did not. A clock-synchronous monitor is a second
> receiver carrying the same assumption, not an independent observer — the
> loopback fallacy moved from the driver to the observer. vplan v5 now forbids
> it as F7's oracle; what does not yet exist is a monitor with its own
> timebase. The honest version also needs the two decoders' disagreement rate
> reported as a **result** rather than as errors.

## What is being built

`UartSerialMonitorIndep`: a monitor that never references `dut.clk`. It waits
for a falling edge **on the pin** (a physical event, not a clock event), then
advances with `Timer` in picoseconds using its **own** nominal bit period,
derived from the spec and from the programmed `BAUD_DIV` — never from the
driver's `bit_ps`, which carries the injected error. Under a driven baud error
it therefore drifts relative to the transmitter exactly as a real link partner
would.

## Questions

**Q1 — is the +0.50% window displacement the DUT's, or the measurement's?**
09-27 measured the DUT's 8N1 window as 10.75% wide at both `BAUD_DIV` values
with its **centre displaced +0.50%**, and offered `rx_sync`'s one-clock delay
as a candidate mechanism. An observer with its own timebase has no `rx_sync`
and no oversampler. Prediction: the **independent monitor's own window is
symmetric**, centre within ±0.25% of zero, which would locate the +0.50%
displacement **in the DUT** rather than in the measurement path. Fails if the
independent monitor's window is also displaced by ≥0.25% in the same
direction.

**Q2 — the independent observer's window width, derived before it is measured.**
A mid-bit sampler that locks once on the start edge and then counts its own
nominal bit periods samples the 8N1 stop bit 9.5 bit periods after the edge it
locked to. It mis-samples when the accumulated error reaches half a bit, so its
budget is `0.5/9.5 = 5.263%` either side and its window is **10.53% wide**.
Prediction: measured width within **±0.30%** of 10.53%, i.e. one 5 bp grid step
of slack plus edge-detection granularity. Stated with a number so it can fail.

**Q3 — THE UNCOMFORTABLE ONE. Is a naive independent observer even a valid
oracle?** The DUT's measured window is **10.75%** wide and Q2 predicts the
observer's is **10.53%** — *narrower*. If so, then across roughly `±0.11%` of
eps at each edge of the DUT's window the observer fails where the DUT succeeds,
and a disagreement there is evidence about **the observer**, not the DUT.
Prediction: the observer's window is narrower than the DUT's, so **replacing a
clock-synchronous observer with a naive independent one does not by itself give
F7 a valid oracle** — it exchanges a correlated observer for an under-budgeted
one. Prediction of an awkward result, stated so it can fail: if the observer's
window comes out *wider* than the DUT's, Q3 is wrong and the naive monitor is
sufficient.

**Q4 — the disagreement rate, as a result rather than as errors.** 09-27's
clock-synchronous monitor disagreed with the DUT on **5 of 1274** checks
(0.39%) across ±7% of eps. Prediction: the independent observer disagrees on
**at least 5% of checks** over the same span, because it genuinely drifts,
and the disagreements are **concentrated at the extremes** of the eps sweep
rather than spread through it. Both numbers stated so both can fail.

**Q5 — does an edge-timestamp recorder fix what Q3 breaks?** The fix for an
under-budgeted observer is not a better sampler but a different kind of
instrument: record every transition's **timestamp** and decode offline, so the
decision is arithmetic rather than a sample at a committed instant, and the
observer's margin can be **reported with every frame** instead of being
implicit. Prediction: such a recorder decodes correctly over the DUT's entire
window **and beyond it**, i.e. its effective window strictly contains the
DUT's, making it a valid oracle where the naive monitor is not; and its
reported per-frame margin shrinks monotonically as |eps| grows.

## Checks (each against an exactly known value or a deliberate provocation)

- **V1 — exact agreement at zero error.** At `eps = 0` and `phase = 0` all
  three decoders (DUT, clock-synchronous monitor, independent monitor) must
  agree on **every** frame. Not "mostly": a single disagreement at zero error
  means the independent monitor is broken, not that it is independent.
- **V2 — the independent monitor must not reference the clock.** Asserted
  structurally, not by comment: the monitor's source is searched for
  `dut.clk`, `RisingEdge` and `FallingEdge(` on a clock, and the check fails if
  any appears. A claim about a timebase that is enforced only by intention is
  not enforced.
- **V3 — MUTATION, because 09-27 established that this is the only defence
  that works.** Break the independent monitor's own bit period by one part in
  fifty and require the frames it decodes to change. A monitor that decodes
  identically with the wrong period is not measuring what it claims to.
- **V4 — MUTATION OF THE DUT, on a copy.** Shift the DUT's sampling point by
  one oversample tick in a copy of the RTL and require the independent
  observer to notice. This is the check the clock-synchronous monitor is
  structurally unable to make, since it would shift with it.
- **V5 — the margin is reported, and its sign is checked.** The recorder's
  per-frame margin must be positive for every frame it decodes correctly and
  must cross zero no later than the first frame it decodes incorrectly. An
  oracle that cannot say how close it came to being wrong is the thing this
  session is trying to stop building.

## What this session will NOT claim

The DUT is not expected to be wrong. 09-25 and 09-27 both measured its F7
window and it is inside the plan's requirement. Everything above is about
whether the **instrument** that measures that window is entitled to its
verdict, and the expected outcome is a **narrowing of what F7's sign-off may
rest on**, not a change to the DUT. Superseded vplan text will be annotated in
place, per the standing rule, and not deleted.
