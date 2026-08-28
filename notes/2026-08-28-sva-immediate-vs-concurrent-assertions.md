# Study Notes: SystemVerilog Assertions — Immediate vs. Concurrent

**Date:** 2026-08-28
**Progress.md item:** Phase 2, "Basic SVA (`assert property`, immediate
vs. concurrent)" — the item after functional coverage (completed
2026-08-26, second session). Per that session's recommendation ("confirm
with a minimal repro before designing that session's example, exactly as
this session and the previous one did"), this session opened with
minimal repros of both immediate and concurrent assertions before
writing any example code.

## 0. Environment note: this session had root/apt access, unlike prior sessions

This session's container had no `iverilog` preinstalled, but — unlike the
2026-08-22/23 sessions that motivated writing
`tools/setup_iverilog.sh` (a no-root .deb-extraction workaround, per that
script's own header) — this session's container *did* have working root
and `apt-get` access: `apt-get install -y iverilog gtkwave` succeeded
directly. The distribution package pulled in was **Icarus Verilog 12.0**,
a different major version from the 10.3 that `tools/setup_iverilog.sh`
pins and that every prior session's tooling-gap finding in this repo was
established against. This is a real, if minor, inconsistency worth
flagging: the sandbox this repo's daily automation runs in is not
identical session-to-session (sometimes root-less, sometimes not; the
distribution default `iverilog` version can differ), so a version pin
matters for keeping tooling-gap findings comparable over time.

Rather than let an environment accident silently change which Icarus
Verilog version this repo's whole accumulated body of tooling notes is
about, this session used `tools/setup_iverilog.sh` (confirmed via
`iverilog -V` → `Icarus Verilog version 10.3 (stable)`) as the
authoritative toolchain for today's actual example and findings below,
and treats the apt-installed 12.0 result as a secondary, clearly-labeled
data point (Section 3) rather than the headline finding — so today's
"confirmed on this build" claims stay directly comparable to
2026-08-22 through 2026-08-26's.

## 1. Standard concepts (independent of the tooling finding below)

- **Immediate assertions** (`assert (expr) else action;`, also
  `assert #0 (expr)` for a "final settled value" flavor) are procedural
  statements — they go inside `initial`/`always` blocks (or module-level
  procedural contexts) and evaluate `expr` once, at the point of
  execution, like an `if` with a built-in "this is a correctness check,
  not a design branch" semantic. They are the assertion equivalent of the
  hand-written `if (!cond) $error(...)` idiom this repo has used since
  2026-08-23 (when immediate assertions were first found unavailable).
- **Concurrent assertions** (`assert property (@(clocking_event)
  property_expr) else action;`) are evaluated over time, sampled at a
  clocking event (almost always `@(posedge clk)`), and are built from
  **sequences** (temporal patterns of boolean expressions, e.g. `a ##1 b`
  = "a this cycle, b the next cycle") and **properties** (sequences
  combined with implication operators, most commonly the overlapping
  implication `|->` and non-overlapping `|=>`: `antecedent |-> consequent`
  reads as "whenever the antecedent sequence matches, the consequent
  sequence must also match"). Concurrent assertions are the
  industry-standard tool for protocol checking (e.g. "a request must be
  followed by an acknowledge within N cycles": `req |-> ##[1:N] ack`)
  because, unlike an immediate assertion, they naturally express a check
  spanning multiple clock cycles without hand-written state-tracking
  code — exactly the kind of check this repo's `sync_fifo` full/empty
  protocol violations (2026-08-23) or the ALU's request/valid timing
  would be expressed with, on a simulator that supported them.
- **`disable iff (reset_expr)`**: the standard way to suppress a
  concurrent assertion during reset/known-invalid periods, since a
  property mid-evaluation across a reset edge would otherwise produce
  spurious failures.
- **`assert` vs. `assume` vs. `cover`**: the same property syntax is
  reused for three different purposes — `assert property (p)` checks `p`
  holds (simulation: flags violations; formal: proves/disproves it),
  `assume property (p)` *constrains* the environment to only produce
  stimulus consistent with `p` (meaningful mainly to a formal tool, which
  uses it to restrict the input space it explores), and
  `cover property (p)` tracks whether `p` was ever *exercised* (a
  reachability/coverage question, not a correctness one) — a third
  category this repo has not covered at all and will return to in
  Phase 5 (formal verification), where `assume`/`cover` are used far more
  heavily than in simulation-only SVA use.
- **Why assertions matter beyond "another way to write a check"**: an
  assertion embedded at the point in the RTL/testbench where a protocol
  rule actually lives (e.g. inside the DUT itself, or a bound checker
  module) fires the instant the rule is violated, with the exact
  simulation time and the values that caused it — versus a scoreboard
  that only compares end-of-transaction results and may need real debug
  work to trace a wrong output back to the cycle that caused it. This
  "fail fast, fail local" property is the main practical reason
  assertion-based verification is considered a distinct discipline from
  pure input/output scoreboard checking, not just syntactic sugar for the
  same check — a point worth understanding even while working around the
  syntax not being available on this build (Section 3's checker example
  is architected with this principle in mind: a separate, dedicated
  checker component bound alongside the DUT, not inline ad hoc checks
  scattered through a stimulus-generating testbench).

Source for the above: standard SystemVerilog Assertions (SVA) usage as
covered by the IEEE 1800-2017 LRM (Clause 16, "Assertions") and by
Sutherland/Bergeron/Spear-lineage SVA tutorial material already cited
elsewhere in this repo's notes (e.g. Sutherland's *Verilog HDL Coding
Styles*, cited since 2026-08-22). This is stable, standard-reference
material — WebSearch/WebFetch were available this session but not used
for this section, matching the same "stable LRM material doesn't need a
live search" judgment made in the 2026-08-26 randomization note.

## 2. Tooling finding on this repo's established baseline (Icarus Verilog 10.3)

Both repros were run standalone in `/tmp/repro/` (not committed, per this
repo's established practice) before any example code was designed,
against the genuine pinned `tools/setup_iverilog.sh` toolchain.

1. **Immediate assertions: confirmed still NOT implemented**, consistent
   with the 2026-08-23 finding (re-verified rather than assumed, per
   2026-08-26's recommendation to always check first):

   ```
   immediate_assert_only.sv:6: sorry: Simple immediate assertion statements not implemented.
   immediate_assert_only.sv:9: sorry: Simple immediate assertion statements not implemented.
   ```

   A separate repro of the `assert #0 (expr);` variant fails even earlier,
   at the parser level (`syntax error` / `malformed statement`), so
   neither immediate-assertion flavor works on this build.

2. **Concurrent assertions (`assert property`): also NOT supported**,
   with a cleaner failure mode than most gaps found in this repo to date:

   ```
   concurrent_simple.sv:6: syntax error
   concurrent_simple.sv:6: error: malformed statement
   concurrent_simple.sv:6: sorry: concurrent_assertion_item not supported. Try -gno-assertion to turn this message off.
   ```

   i.e. Icarus's parser *recognizes* `assert property` as a distinct
   grammar category (unlike, say, `covergroup` on this same 10.3 build,
   which the parser doesn't recognize as a keyword at all — see
   2026-08-26's note) and explicitly declines to implement it, even
   naming a compiler flag that acknowledges the feature's existence
   (`-gno-assertion` — note the flag name is singular here, `-gno-
   assertion`, distinct from Icarus 12.0's `-gno-assertions`/
   `-gsupported-assertions`, per Section 3 below; flag naming itself
   changed between the two Icarus versions). A separate repro confirmed
   a standalone named `property ... endproperty` declaration block
   (outside any `assert` statement) does not parse either.

**Net result: on this repo's established 10.3 toolchain, NEITHER
immediate NOR concurrent SVA syntax is available at all** — a bigger,
cleaner-cut gap than most 2026-08-23 through 2026-08-25 findings (which
had partial-support nuances), in the same category as 2026-08-26's
`randomize()`/`covergroup` findings: an entire IEEE 1800 language area
absent from this build, not a partial implementation with a workaround
at the syntax level. Section 3's example therefore uses the same
`if (!cond) $error(...)` idiom already established since 2026-08-23,
architected as a dedicated assertion-style checker (see Section 1's last
bullet) rather than as inline stimulus-testbench checks, since that
architectural distinction is itself real, useful content independent of
which concrete syntax expresses it.

## 3. Secondary finding: behavior on Icarus Verilog 12.0 (this session's apt-installed version)

Documented here for completeness and because it is genuinely useful
forward-looking context, but explicitly NOT the basis for today's
committed example (see Section 0 for why):

- **Immediate assertions work** on 12.0 — the same repro that failed on
  10.3 compiles and runs correctly, including reporting a deliberately
  failing case with the right message and simulation time:
  ```
  ERROR: immediate_assert_only.sv:9: EXPECTED-FAIL: immediate assert correctly caught a==0
         Time: 2  Scope: immediate_assert_only
  ```
- **Concurrent assertions still do not work** on 12.0 either — same
  category of explicit "sorry: concurrent_assertion_item not supported"
  rejection, just with slightly different flag names offered
  (`-gno-assertions` / `-gsupported-assertions`, plural, vs. 10.3's
  singular `-gno-assertion`).
- Icarus Verilog's own project documentation describes concurrent SVA
  support as a longstanding, only-partially-implemented area of the tool
  across versions, consistent with both findings above. Given this,
  Phase 5 (Assertions & Formal Verification), which fundamentally needs
  real concurrent/formal property checking, will need a different tool
  regardless of which Icarus version ends up available in a future
  session's container — SymbiYosys/Yosys (already planned for the formal
  milestone per the README) remains the right plan.
- Practical implication for future sessions: if a future session's
  container happens to default to a newer Icarus Verilog via plain
  `apt-get install iverilog` (as this session's did), immediate
  assertions could be retrofitted into this repo's existing `if/$error`
  checks with real `assert` syntax — but only by explicitly choosing to
  move off the pinned 10.3 baseline this repo's whole tooling-gap history
  is built on, which is a call worth making deliberately (and
  documenting clearly, updating `tools/setup_iverilog.sh` itself) rather
  than by accident of which version a given day's apt mirror serves up.

## 4. What today's example demonstrates given (2)

`examples/phase2/alu_sva_checker.sv`:

- Retrofits the reused, unmodified `alu_dut` (from `alu_if_and_dut.sv`)
  with a genuinely **independent reference model** (not a copy of the
  DUT's own combinational expressions: carry/borrow computed via
  comparison rather than a widened add/subtract, overflow computed via a
  sign-extended-truncation check rather than a sign-bit XOR) and checks
  DUT outputs against it every cycle.
- Is structured as a **dedicated checker task/module**, separate from
  stimulus application, deliberately mirroring how a real concurrent-
  assertion-based checker would be organized (one check per invariant,
  triggered every time new data is valid) even though the underlying
  syntax is the established `if (!cond) $error(...)` idiom rather than
  `assert`/`assert property` — the architectural point (checker as a
  distinct, DUT-adjacent component) is real and portable even though
  today's build can't express it with native assertion syntax.
- Includes one deliberate, clearly-labeled expected-failure case
  (mirroring `sync_fifo_directed_tb.v`'s illegal-push/illegal-pop pattern
  from 2026-08-23) — a directed vector where the checker is deliberately
  given a wrong expected value, proving the check actually fires and
  reports correctly rather than only ever being shown passing.

## 5. Open items after this session

- Decide deliberately (not by environment accident) whether to move this
  repo's pinned toolchain from Icarus Verilog 10.3 to a newer version —
  12.0 gains immediate assertions (and possibly other closed gaps,
  untested) but concurrent assertions remain unavailable either way, so
  the case for moving is weaker than it might first appear. Not decided
  today; flagged for a deliberate future session rather than changed
  incidentally.
- If/when a version move happens, retrofit `alu_manual_constrained_
  random.sv`, `alu_manual_functional_coverage.sv`, and today's
  `alu_sva_checker.sv` (plus the Phase 1 testbenches) from `if/$error` to
  real `assert` statements, and re-test whether `randomize()`/
  `constraint`/`covergroup` also newly work — not assumed, given this
  repo's repeated experience that "not supported" findings are
  build-specific rather than universal.
- `assume property` / `cover property` were not separately tested
  (concurrent assertions of any kind are unsupported per Section 2, so
  this follows immediately without a separate repro) — revisit in
  Phase 5 alongside the SymbiYosys/Yosys tooling that phase already
  plans to use.
- Phase 2's final remaining checklist item after this session is the
  phase milestone itself: "constrained-random SV testbench w/ scoreboard
  + coverage for a small DUT" — combining the manual-workaround
  randomization (2026-08-26), functional-coverage (2026-08-26 second
  session), and now the assertion-style checker (this session) into one
  integrated testbench, rather than the separate demonstration files that
  exist today.
