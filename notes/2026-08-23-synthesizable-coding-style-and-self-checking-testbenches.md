# Phase 1 Study Notes: Synthesizable Coding Style & Self-Checking Testbenches

**Date:** 2026-08-23
**Roadmap item:** Phase 1 — Digital Logic & HDL Fundamentals
**Covers checklist item:** "Synthesizable coding style + simple
self-checking testbenches"

**Note on tooling — resolved this session:** the 2026-08-22 session found
no way to install Icarus Verilog (`apt-get install` fails on a dpkg lock
permission error, and no conda/pip alternative exists). This session
found a working root-free path: Icarus Verilog's Ubuntu 22.04 ("jammy")
`.deb` package can be downloaded directly from the Ubuntu archive and
extracted with `dpkg-deb -x` (which only unpacks files to a target
directory and does not require install privileges), giving working
`iverilog`/`vvp` binaries. The two helper libraries (`ivlpp`, `ivl`) and
`.vpi` modules that `iverilog`/`vvp` normally expect at a fixed system
path need `-B <extracted>/usr/lib/x86_64-linux-gnu/ivl` (compile) and
`-M <extracted>/usr/lib/x86_64-linux-gnu/ivl` (simulate) to be pointed at
the extracted, non-standard location. This is now scripted in
`tools/setup_iverilog.sh` so future sessions do not need to
rediscover it. Both this session's new example
(`examples/phase1/priority_encoder_style_and_testbench.v`) and the
2026-08-22 shift-register example were compiled and run this session;
captured console output is committed alongside each
(`examples/phase1/priority_encoder_sim_output_2026-08-23.txt`,
`examples/phase1/shift_register_sim_output_2026-08-23.txt`) as real
evidence rather than hand-derived expected behavior. Both matched their
previously hand-derived expected behavior exactly, which is a useful
independent confirmation that the manual semantic reasoning in the
2026-08-22 notes was correct.

## 1. Why "synthesizable coding style" is its own topic (not just "correct Verilog")

A verification engineer needs synthesizable-style fluency for two
distinct reasons, beyond simply being able to read RTL:

1. **A large fraction of real verification bugs are actually synthesis/
   simulation mismatches**, not functional bugs in the design's intended
   behavior — code that simulates one way but synthesizes to different
   (or ambiguous/non-deterministic) hardware. Recognizing these patterns
   in code review or when triaging an unexpected result is a core
   verification skill, not just a design skill.
2. **Testbenches themselves must NOT be synthesizable** (they use
   `initial` blocks, `#delay` timing, `$display`, dynamic memory, etc.
   freely) but need to correctly stimulate and check DUT code that *is*
   synthesizable — so a verification engineer needs a clear mental model
   of exactly where that boundary is, to know what's fair game in a
   testbench vs. what would be a red flag if seen in RTL.

## 2. Synthesis/simulation mismatch patterns (the practical checklist)

These are the patterns most commonly responsible for "it simulates fine
but the real chip doesn't work" bugs, and are the actual reason
synthesizable-style rules exist (not just style preference):

- **Incomplete sensitivity lists in `always @(...)` blocks.** A manually
  written sensitivity list missing a signal that's read inside the block
  causes simulation to show stale values on an edge the list doesn't
  cover, while synthesis (which infers combinational behavior from the
  block's *contents*, not the list) builds hardware that responds to
  every input regardless. **Fix:** always use `always @(*)` for
  combinational logic (Verilog-2001+); never hand-write combinational
  sensitivity lists.
- **Incomplete `if`/`case` branches in combinational blocks infer
  latches.** If a combinational `always @(*)` block does not assign a
  signal on every possible path through the code (e.g. an `if` with no
  `else`, or a `case` with no `default` and not all case values covered),
  synthesis must infer a latch to hold the previous value on the
  unhandled path — almost never the design intent, and a classic
  interview/code-review red flag. **Fix:** give every combinational
  output a default assignment at the top of the block, then let
  subsequent conditional logic override it; ensure every `case` has a
  `default`.
- **Mixing blocking and non-blocking assignments to the same signal, or
  within the same always block for sequential logic**, per the
  2026-08-22 notes: assign every signal driven by a given `always` block
  using only one assignment type, and use `<=` exclusively for anything
  meant to represent a clocked register.
- **Using `#delay` timing controls in RTL.** `#5` etc. has no synthesis
  meaning (synthesis tools ignore delay values entirely) and exists
  purely as a simulation-time modeling construct; delays belong only in
  testbenches (clock generation, stimulus timing) or in gate-level
  post-synthesis netlists annotated by SDF back-annotation, never in
  RTL describing design intent.
- **Multiple drivers on the same signal from different always
  blocks/continuous assignments.** Synthesizable RTL requires each
  signal to have exactly one structural driver; simulation may or may
  not flag a conflict clearly depending on tool and signal type
  (`wire` contention is a classic silent bug), while synthesis will
  either error or produce unintended resolution logic.
- **Combinational feedback loops** (a combinational signal that
  feeds back into its own cone of logic without passing through a
  register) can simulate as an oscillation, a race-dependent stable
  value, or an infinite delta-cycle loop depending on simulator
  scheduling — behavior that is simulator-dependent and essentially
  never synthesizable to sane hardware. **Fix:** every feedback path in
  a state machine or accumulator must pass through a registered
  (non-blocking, clocked) element.
- **Reset style consistency.** Asynchronous reset
  (`always @(posedge clk or negedge rst_n)`) and synchronous reset
  (`always @(posedge clk) if (!rst_n) ... else ...`) are both valid and
  widely used industrially, but mixing styles inconsistently across a
  design complicates static timing analysis (async reset needs explicit
  reset-recovery/removal timing checks) and, more relevant to
  verification, complicates writing a single consistent reset sequencing
  task across a testbench that stimulates multiple DUT instances with
  different reset conventions. A verification plan should state which
  reset style each DUT boundary uses and check it is respected.

## 3. Self-checking testbench structure (the pattern used going forward)

A "self-checking" testbench, as distinct from a testbench that merely
prints signal values for a human to eyeball, has three structural
components, all present already (informally) in the 2026-08-22 shift-
register example and formalized here as the pattern this roadmap will
reuse and grow (toward class-based SystemVerilog testbenches in Phase 2):

1. **Stimulus generation** — drives DUT inputs, ideally via a reusable
   `task` rather than copy-pasted inline code, so the same stimulus
   sequence can later be parameterized/randomized (Phase 2) without
   restructuring the testbench.
2. **A reference model** — an independent, behavioral (non-RTL, non-
   synthesizable-style) computation of the expected output, written from
   the specification rather than by mirroring the DUT's implementation
   structure. This independence is the entire point: a reference model
   that happens to make the same implementation mistake as the DUT
   provides zero verification value. For the example below, the
   reference model is a plain Verilog function computing the
   specification's arithmetic directly, deliberately structured
   differently from the DUT's priority `casez` chain.
3. **A checker** — compares DUT output against the reference model
   output every relevant cycle and increments an error counter (rather
   than immediately calling `$finish` on the first mismatch), so a
   single simulation run reports the *total* number of mismatches rather
   than stopping at the first one — important for triaging how
   widespread a bug is, not just whether one exists. The testbench
   reports a clear PASS/FAIL summary based on the final error count and
   sets a non-zero exit indication on failure (important once this
   testbench pattern is later wired into a regression script, per the
   Phase 6 "surrounding flow" roadmap item).

## 4. Example: priority encoder (deliberately chosen for latch-inference risk)

A 4-input priority encoder is a good vehicle for this topic because the
*naive* way to write it is exactly the incomplete-case-statement pattern
described in Section 2 (a `case`/`casez` without a `default`, since a
constant "no valid input" case is easy to forget), making the good-vs-bad
contrast concrete rather than abstract. The companion file
(`examples/phase1/priority_encoder_style_and_testbench.v`) contains:

- `priority_encoder_correct` — synthesizable-style-clean version: default
  assignment at top of the combinational block, full `casez` coverage
  including an explicit no-valid-input case, `always @(*)`.
- `priority_encoder_latch_bug` — deliberately buggy version: the
  no-valid-input case is omitted from the `casez`, so `valid` and `enc`
  are only assigned in 4 of the 5 possible input conditions; a synthesis
  tool would infer latches for both outputs on the omitted path (in
  simulation, Icarus Verilog will typically retain the previous value on
  that path too, but this is exactly the kind of code where relying on
  a particular simulator's specific latch-modeling behavior instead of
  fixing the missing case is the mismatch risk described in Section 2).
- A self-checking testbench that exhaustively drives all 16 possible
  4-bit inputs, computes expected `(valid, enc)` from an independent
  reference task, and checks both DUT variants against it every cycle.
  **Verified by simulation this session** (see the tooling note above):
  `priority_encoder_correct` passes all 16 vectors; `priority_encoder_latch_bug`
  fails exactly the all-zero-input vector, with both outputs reading `'x'`
  (undefined) rather than the specified `valid=0` — because that vector
  happens to be tested first in this testbench's 0..15 sweep, so the
  unassigned signal path has never been driven yet, rather than
  "retaining a stale prior value" as might happen with a different test
  order. This order-dependence is itself an important, easy-to-miss
  point about latch-inference bugs, discussed in the code comments.

## 5. Progress

Marked "Synthesizable coding style + simple self-checking testbenches"
done in `progress.md`. The remaining Phase 1 item is the milestone
deliverable (synchronous FIFO or FSM design + directed testbench) —
natural next step now that both the assignment-semantics (2026-08-22) and
synthesizable-style/self-checking (today) foundations are in place;
ideally attempted on a session where `iverilog` is available so the
milestone testbench's pass/fail output can be committed as real evidence.

## References

Content in this note reflects standard, stable digital-design/HDL
knowledge (IEEE 1364/1800 synthesizable-subset conventions as commonly
taught and used industrially — e.g. Sutherland/Mills-style "Verilog and
SystemVerilog Gotchas" latch-inference and blocking/non-blocking
guidance, and standard synthesis-tool user-guide synthesizable-subset
definitions) rather than time-sensitive information, so it was written
directly without WebSearch, consistent with the 2026-08-22 session's
approach to comparable foundational-HDL content. WebSearch was available
this session but was not used for this reason.
