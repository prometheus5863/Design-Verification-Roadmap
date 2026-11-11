# A structural CDC checker, and the partition it makes with simulation

**2026-11-11.** Takes the ranked-second item of 2026-11-10,
*A CRUDE STRUCTURAL CDC CHECKER*. The instrument is
`tools/cdc_structural_check.py` (25/25 self-test, 9/9 mutants on its own
source). The result the item was created for arrived on the first run, and
the more interesting result is what the tool **cannot** see.

---

## 0. Why this and not the ranked-first item

11-10 ranked a metastability-injection synchroniser model first and this
second. This session took the second, and the reason is recorded rather than
glossed:

- Both items exist for the same purpose — to make mutant `C7` observable.
- This is the cheaper route. The injection model is a stochastic timing model
  with seeds and sweeps; this is a file reader.
- **Its acceptance test was already written**, on 2026-11-10, before the tool
  existed: *"run it on `examples/phase6_cdc_basics/cdc_crossings.v` with each
  of the seven mutants applied, and require it to flag `C7`"*. A tool with a
  mutation suite waiting for it before a line is written is a rare thing to
  find on a standing list.
- The injection model's own acceptance criterion is that it makes `C7`
  **detected**, which by design makes the existing CDC mutation harness go
  red on its pinned expectation. Landing a new instrument and invalidating an
  old one's pin in the same session makes both harder to read.

The ranked-first item is carried, unchanged and unretired.

---

## 1. What a structural checker is for

The 11-10 entry's conclusion was already written:

> **CDC is a structural property and belongs to a static CDC checker, not to
> simulation.** A green simulation of a multi-bit crossing is evidence of
> almost nothing.

and `C7`'s expected-survivor reason said what the tool would do:

> A structural CDC checker catches this in one pass by noticing that
> `toggle_src` feeds destination logic on an unsynchronised path — which is
> the argument for owning such a tool, made by a defect rather than by
> assertion.

It does, by rule R1, on the first run.

## 2. The partition, which is the real result

The seven CDC mutants, by which instrument sees them:

| mutant | what it breaks | simulation | structure |
|---|---|---|---|
| C1 | 2FF becomes 1FF | detected (`L1`) | detected (**R2**) |
| C2 | Gray encoder shifts by 2 | detected (`G1`) | — |
| C3 | Gray decoder drops the XOR | detected (`G1`) | — |
| C4 | Gray encoder is the identity | detected (`G1`) | — |
| C5 | toggle latches instead of toggling | detected (`P2`) | — |
| C6 | edge detector sees rising only | detected (`P2`) | — |
| C7 | synchroniser bypassed | **expected survivor** | detected (**R1**) |

Simulation 6, structure 2, **union 7, overlap exactly C1.**

The two instruments are nearly disjoint, and the reason is not an accident of
these seven mutants. Simulation here measures *functional* properties —
coherency, pulse accounting, latency — and C2–C6 are functional defects in
coding and decoding. C7 changes *which flop can go metastable*, which is not
a function of any waveform a zero-delay simulator can produce. C1 is the only
mutant that is both: a one-flop synchroniser is structurally wrong and also
changes the latency `L1` pins.

So the honest claim is not "the structural checker is better". It is that a
repository with only one of the two has a blind spot the size of the other,
and until today this one had a blind spot shaped exactly like `C7`.

**Check `6e` asserts the partition**, not merely the detection. If a later
change makes the structural checker start claiming C2–C6, the suite fails. An
instrument that flags everything catches `C7` too, and that is not the same
achievement.

## 3. The four rules, and their controls

| rule | fires on | positive control | negative control |
|---|---|---|---|
| R1 RECONVERGENCE | a net feeding a synchroniser **and** read by clocked logic in the same module | `PLANT_R1`, and C7 | `PLANT_CLEAN` |
| R2 SYNC_DEPTH | a synchroniser under two flop stages | `PLANT_R2`, and C1 | `PLANT_CLEAN` |
| R3 MULTIBIT_SYNC | a multi-bit 2FF with no Gray encoder ahead | `PLANT_R3`, and `u_sync_bin` in the real TB | the Gray crossing beside it |
| R4 UNSYNC_CROSSING | a register in one domain read by a register in another | `PLANT_R4` | `PLANT_R4_CLEAN` |

**R4 fires on nothing in this repository.** Every crossing here is
synchronised. Without `PLANT_R4` it would be four rules of which one had
never been shown to work — and without `PLANT_R4_CLEAN` it would be a rule
never shown to *discriminate*, which is the weaker and commoner failure.

## 4. On the repository: one finding, and it is the right one

41 `.v` files, **one** finding:

```
R3_MULTIBIT_SYNC cdc_crossings_tb.v:174 [cdc_crossings_tb]
  synchroniser `u_sync_bin` carries 8 bits and its data input `bin_skewed`
  is not driven by a Gray encoder [structural]
```

That is the deliberate wrong crossing the CDC example exists to be wrong
about, and the correct Gray crossing on the next line is **not** flagged.
Checks `7b` and `7c` assert both halves, because a checker that flagged both
would look identical on the summary line and be useless.

## 5. Six defects found by running it, two found only by the plants

Running it found six:

1. **The instance regex had no word boundaries.** On `if (!rst_n) begin` it
   matched module `i`, instance `f`, and the `(` after — then consumed every
   line to the next `);`, swallowing an `endmodule` and two whole modules.
   *Three of five modules in `cdc_crossings.v` disappeared from the parse.*
   A structural checker that silently loses modules reports a clean file,
   which is the worst failure available to it.
2. **The reset arm never closed.** `end else begin` nets to the same brace
   depth and the test ran before the update, so every assignment in
   `cdc_sync_2ff` was classified as reset logic and R2 saw a zero-stage
   synchroniser.
3. **`else if (pulse_src) toggle_src <= ~toggle_src;` recorded its target as
   `else`** — in the one module whose entire job is the toggle.
4. **`initial` did not end the open always block**, so a 200-line checking
   `initial` had its reads attributed to a one-line `always @(posedge
   clk_b)`. That produced two R1 false positives in the testbench — a
   testbench reading its own signals. *A false positive in a lint tool is not
   a harmless extra line: it is the reason people stop reading the output.*
5. **Name matching is not enough, and here is the number.** Over all 41
   files the name test produced three findings, of which **two were
   `sync_fifo`** — a *synchronous FIFO*, matched because its name begins
   `sync_`. 33 % precision, both false positives the same module.
   `is_synchroniser()` is now structural: a synchroniser is a flop chain
   whose every non-reset assignment copies one net. `sync_fifo` fails on its
   pointer arithmetic. `build_db()` lets an instance of a module defined in
   another file be judged structurally, and findings print `[structural]` or
   `[name-only]` so a guess is never presented as a measurement.
6. **The Gray exemption compared against the encoder output net itself.**
   The testbench feeds its Gray synchroniser from `gray_skewed`, the skew
   model's copy of `gray_a`, so the exemption missed — and the checker called
   the textbook-correct half of a side-by-side right/wrong demonstration a
   defect.

Two more only the planted controls could find, because every module in this
repository happens to avoid them:

7. **A port line carrying two directions** gave every name the first one. So
   `input wire [W-1:0] d_src, output wire [W-1:0] q_dst);` made `q_dst` an
   **input**, the module had no outputs, and **R2 — whose entire job is to
   walk from an output back to an input — never ran** on any module declared
   that way. The suite was 25/25 with a dead rule in it.
8. **One line holding several statements** recorded the first and dropped the
   rest, so a one-line reset style left the flop chain with no second stage
   and `is_synchroniser()` saw a module with no flops.

Defects 7 and 8 are why §6 exists.

## 6. Mutation-testing the instrument

`tools/cdc_structural_check_mutation.py` injects nine defects into the
checker's **own source** and requires `--selftest` to go red for each.
9 detected, 0 survived, 0 anchors lost.

Six of the nine are the defects above, pinned so they cannot return silently.
Three are rule-logic defects that were never present (R1 disabled, R2's
threshold off by one, R3 treating an unresolvable width as safe).

Two properties of the harness are deliberate:

- **A non-green baseline stops the run.** Every mutant verdict after one is
  meaningless. That check fired on the first attempt: the mutant copy lives
  in a temp directory and the self-test walks the repository from `__file__`,
  so the copy found no `.v` files and failed on the unmutated baseline. The
  checker grew a `--root` argument rather than the harness growing a way to
  ignore the failure.
- **A mutant whose anchor text is gone is `ANCHOR LOST` and counts as a
  failure**, not a skip. Harness-versus-subject drift is a recorded theme
  here, and a silent skip is how it stays invisible.

## 7. What it cannot do, stated up front and not as an apology

No elaboration, no generate blocks, no `define`, no hierarchy beyond the
module database, parameters resolved only from literal declarations in the
same module, synchronisers recognised only when instantiated as a module
(never inline). A net's domain is inferred only from the clock of the block
that drives it, so a module *input's* domain is unknown — which is exactly
why R1 is phrased as **reconvergence** rather than as "crosses a domain".

Those limits are the reason the self-test asserts what the checker must *not*
flag as hard as what it must.

## 8. What this leaves open

- **The metastability-injection model is still the right next item**, now
  with a sharper purpose: not to make `C7` visible (it is visible), but to
  measure how often it *matters*, which structure cannot say.
- **R4 has no real instance.** It is a correct rule with a planted control
  and nothing in this repository to find. The async FIFO on the standing
  list would give it one.
- **`[name-only]` has never been exercised on a real file**, because every
  `.v` file here is scanned together. A single-file invocation would.
- **Run it in `run_all_harnesses.sh`.** That runner already fails to reach
  two of 11-10's runners; this commit adds two more, making it the
  seventeenth session for that item and the ninth recorded growth in the set
  it does not cover.
