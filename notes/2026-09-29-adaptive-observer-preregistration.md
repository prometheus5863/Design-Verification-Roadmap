# Pre-registration: an observer that re-derives the bit period per frame

**2026-09-29, written and committed BEFORE the implementation exists.**
Continuing the practice adopted 2026-09-21 and used on 09-27 and 09-28: state
the predictions with numbers attached, commit them, then build. A prediction
that fails with a number attached is informative; one adjusted after the fact
is not.

## The item

vplan v6 (2026-09-28) records the open requirement:

> What would satisfy containment is an observer that **re-derives the bit
> period per frame from the measured edge spacing**, so its budget comes from
> arithmetic on recorded times rather than from drift against a fixed period.

The disqualification it has to escape is arithmetic. Any observer that locks
once on the start edge and then counts a *nominal* bit period accumulates
`9·ε` of drift by the boundary preceding the last sampled bit, so it has a
budget of exactly `1/18 = 5.5556%` either side, against the DUT's measured slow
limit of **6.75%**. Width is not containment: the DUT's window is displaced
(+1.38% centre) and every fixed-period observer's is centred, so no amount of
extra width helps.

## The design being registered

Per frame, take the start falling edge at `t₀`. Walk the subsequent edges. For
each consecutive pair assign an integer bit-index increment
`Δn = round(Δt / T_ref)`, accumulate `n`, and update `T_ref` to the running
least-squares estimate `T̂ = Σ n·t' / Σ n²` (through the origin, since `t₀` is
itself an edge). Sample at `t₀ + (i + 1.5)·T̂`.

The point of the design, stated before it is measured: the fixed-period
observer's error accumulates over the **whole frame**, whereas this one's
integer assignment can only fail on a **single inter-edge gap**. So the budget
should be set by the largest gap, not by the total span.

## Predictions

**P1 — the budget is data-dependent, and equals `1/(2·g_max)`.**
Writing `g_max` for the largest inter-edge gap in the frame, measured in bit
periods, the adaptive observer decodes correctly for

    |ε| < 1 / (2·g_max)

because the integer assignment `round(Δt/T_ref)` is the only step that can
fail, and it fails when a gap drifts by half a bit. Specific values for 8N1,
LSB-first, with the start bit at n = 0:

| byte | edge positions | `g_max` | predicted budget |
|---|---|---|---|
| `0x00` | fall 0, rise 9 | 9 | **5.56%** |
| `0xFF` | fall 0, rise 1 | 1 | 50% |
| `0xAA` | fall 0, then 2,3,4,5,6,7,8 | 2 | **25%** |
| `0x55` | fall 0, rise 1, then 2..9 | 1 | 50% |

**This is the prediction the session turns on.** If it holds, the observer's
budget is not a property of the observer at all — it is a property of the
**data pattern**, and F7 sign-off has to say which patterns may carry F7
evidence.

**P2 — the observer measures the baud error, to better than 0.05%.**
`T̂/T_nom − 1` is an estimate of the driven `ε`. Within its budget it should
recover `ε` to better than 5 bp (0.05%) absolute, the residual being timestamp
quantisation over the lever arm. This is the check that distinguishes "the
observer re-derives the period" from "the observer got the right answer".

**P3 — containment holds for `g_max ≤ 7` and fails for `g_max = 9`.**
The DUT's window is slow 6.75% / fast 4.00%. `1/(2·7) = 7.14% > 6.75%`, while
`1/(2·8) = 6.25% < 6.75%`. So the observer contains the DUT's window for every
byte whose largest gap is 7 bit periods or fewer, and does **not** for `0x00`.
Containment is therefore achievable — the 09-28 disqualification is escaped —
but **only conditionally**, and the condition is on the stimulus.

**P4 — the 13-point band closes for `0xAA` and does not for `0x00`.**
09-28 found 13 baud errors, +5.60% to +7.75%, at which the DUT receives a clean
frame and the naive independent observer does not. For `0xAA` the adaptive
observer should be clean across all 13. For `0x00` it should fail at the same
points, because `1/(2·9)` is the same 5.56% bound.

**P5 — overall disagreement with the DUT drops below 10%.**
The naive independent monitor disagreed on 18.82% of wide-sweep rows. Averaged
over the trial bytes the adaptive observer should come in **below 10%** but
**not at zero**, because the `0x00`-like patterns are unimproved.

## What would make each prediction wrong in an interesting way

- P1 wrong **low** (budget worse than `1/(2·g_max)`) would mean the
  least-squares update is degrading the estimate rather than improving it —
  i.e. the running `T_ref` update is the wrong order of operations.
- P1 wrong **high** would mean something else is limiting before the integer
  assignment does, most likely the half-bit sampling margin itself, which is
  the fixed-period observer's limit reappearing in a new place.
- P2 failing while P1 holds would be the more interesting outcome: the observer
  would be decoding correctly *without* having actually recovered the period,
  which would mean the containment result is luck.

## The check on the check

Today's other repository produced a rule that applies directly here and is
adopted for this session: **a mutation that does not arrive is
indistinguishable, in the output, from a system that does not respond.** The
09-28 V3 incident was an instance — a mutant too weak to break the thing it
targeted, reported as insensitivity. So every mutation in this session carries
a **positive control on the mutation itself**: an assertion that some quantity
the mutation must reach did in fact move, checked before any zero elsewhere is
interpreted.
