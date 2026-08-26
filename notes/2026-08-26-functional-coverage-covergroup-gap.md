# Study Notes: Functional Coverage (`covergroup`/`coverpoint`/`cross`)

**Date:** 2026-08-26 (second session)
**Progress.md item:** Phase 2, "Functional coverage (`covergroup`/
`coverpoint`/`cross`)" -- the item after Randomization (completed
2026-08-26, first session). Per that session's own recommendation
("the next session should open with minimal repros of `covergroup`
both as a class member and at module level before committing to a
design... could plausibly be entirely unimplemented on this build
rather than partially supported"), this session opened with exactly
that repro before writing any example code.

## 1. Standard concepts (independent of the tooling finding below)

- **`covergroup`**: a container for coverage collection, instantiated
  like a class (`cg = new()`), typically sampled either automatically
  on a clocking event (`covergroup cg @(posedge clk); ... endgroup`) or
  explicitly via `cg.sample()`.
- **`coverpoint`**: tracks the values a single expression takes over
  the simulation. By default SystemVerilog auto-generates one bin per
  distinct value (impractical for a wide bus); real testbenches almost
  always define explicit `bins` to group values into meaningful buckets
  (e.g. `bins low = {[0:63]}; bins high = {[192:255]};`), matching this
  session's approach of a small number of named, meaningful bins rather
  than one bin per raw value.
- **`cross`**: coverage of the *combination* of two or more coverpoints
  -- e.g. `cross op_cp, a_corner_cp;` -- catching gaps a single
  coverpoint's 100% doesn't guarantee (each opcode fully covered AND
  each operand-corner category fully covered does not imply every
  opcode was ever exercised WITH every corner category, which is
  exactly the kind of interaction bug functional coverage exists to
  catch -- e.g. an ALU_SUB-specific borrow bug that only shows up when
  `a` is the corner value 0x00, which a coverpoint-only view could miss
  entirely even at 100% coverpoint coverage).
- **`option.at_least`**: minimum hit count for a bin to count as
  "covered" (default 1). Setting it higher than 1 for individual-value
  coverpoints and leaving it at the default 1 for cross bins (as this
  session's model does) is standard practice -- crosses grow
  combinatorially, so requiring multiple hits per cross bin is often
  impractically expensive to close.
- **Coverage as a stopping criterion.** The primary practical reason
  functional coverage exists in an industrial flow (beyond documenting
  what got tested) is as an objective, automatable stopping criterion
  for constrained-random regression: run randomized tests, sample
  coverage after each, and stop (or escalate to directed tests / a
  biased generator) once the coverage plan's bins are closed, rather
  than running a fixed, arbitrary transaction count. This session's
  example implements exactly that loop (see Section 4).

Source for the above: standard SystemVerilog verification methodology
material, consistent with the same source family used throughout this
repo's earlier notes (Sutherland & Spear, ChipVerify, IEEE 1800 LRM
Chapter 19 concepts) -- general, stable content, not something requiring
a live citation.

## 2. Tooling finding: `covergroup` is entirely unimplemented

Minimal repro (module-scope, kept in `/tmp/repro/`, not committed):

```systemverilog
module cg_module_test;
  logic [2:0] x;
  logic clk;
  covergroup cg_x @(posedge clk);
    coverpoint x;
  endgroup
  cg_x cg = new();
  ...
endmodule
```

Result: `iverilog -g2012` fails at the `covergroup` line itself --
`syntax error` / `error: invalid module item` -- the parser does not
recognize the `covergroup` keyword at all. Since the failure is at the
lexer/parser level (an unrecognized keyword), the identical failure
mode applies whether `covergroup` is declared at module scope or as a
class member -- there is no partial-support case to find here, unlike
several 2026-08-23/24/25 findings (e.g. `always_comb` failing while
plain `always @*` worked). This was confirmed sufficient without a
second class-member repro, since the parser error occurs before any
class-vs-module-scope distinction could matter.

**Conclusion: this Icarus Verilog 10.3 build has no functional coverage
support at all** -- consistent with the growing pattern (starting with
`randomize()`/`constraint` on 2026-08-26 first session) that this
build's practical language support is "Verilog-2001 plus typedef
enum/struct, `always @*`/`@(posedge/negedge)` procedural blocks, and a
significant but partial subset of SV OOP" -- and does NOT include the
constrained-random or coverage halves of IEEE 1800 verification
features. (Icarus Verilog's own documentation confirms coverage and
full constrained-random are known-incomplete areas of its SystemVerilog
support in general, not specific to this particular download/version --
consistent with, not contradicted by, what was found here.)

A second, separate finding while building the example (Section 3 below,
this file's actual repro): `int'(op_raw)` -- an explicit `int` cast of a
`logic [2:0]` value -- crashes the elaborator:
`assert: elab_expr.cc:2630: failed assertion 0`, reported as "cast type
and subject differ in signedness". Repro:

```systemverilog
module cast_test;
  logic [2:0] op_raw = 3'b010;
  int x;
  initial x = int'(op_raw);
endmodule
```

Worked around by using a plain assignment (`int_var = op_raw;`, which
performs the same widen-and-convert without the explicit cast syntax)
instead -- this is the same class of finding as several 2026-08-24/25
gaps: an explicit-cast/explicit-conversion SV syntax form crashes where
the equivalent implicit form works fine.

## 3. What the manual model does and does not reproduce faithfully

`examples/phase2/alu_manual_functional_coverage.sv` hand-implements:
counters per bin (module-level integer arrays, not class properties --
consistent with the 2026-08-26-first-session finding that unpacked
arrays as class properties are broken on this build), an
`at_least`-style closure check per coverpoint/cross, and an overall
percentage as the unweighted mean of the coverpoint/cross percentages
(matching a real covergroup's default `weight = 1` behavior).

This is faithful for the specific case exercised -- fixed, manually
chosen bins and a single cross of two coverpoints -- but does **not**
reproduce, and has no easy equivalent for: automatic per-value bins
(explicit bins were always the realistic choice anyway, per Section 1);
`ignore_bins`/`illegal_bins`; **transition bins** (`(A => B)`, coverage
of a *sequence* of values over time, which has no natural hand-rolled
equivalent without essentially re-implementing a small state machine
per tracked transition); coverage sampled automatically on a clocking
event with automatic re-arming (this model calls `sample_coverage()`
explicitly, once per transaction, rather than on every clock edge);
and per-instance vs. cross-instance (`type_option`) coverage merging
across multiple testbench runs, which is entirely a tool/database
feature with no in-simulation equivalent at all.

## 4. Generator tuning check: corner-draw rate vs. cross-bin closure speed

Before settling on a rate, both a 1-in-4 (same as
`alu_manual_constrained_random.sv`, 2026-08-26 first session) and a
1-in-2 corner-value draw rate for `a` were actually run (the 1-in-2
variant via a throwaway copy in `/tmp/repro/`, not committed) against
`MAX_TRANSACTIONS=4000`, on the theory that the ZERO/MAX `a_corner`
bins and their cross combinations with every opcode are rare under
uniform `a` (each ~1/256) and might need a higher corner-draw rate to
close reliably.

Measured result: **both rates closed all 15 cross bins comfortably**
-- 1-in-4 closed after 252 transactions, 1-in-2 after 384 (1-in-4 was
actually *faster* to close here, the opposite of the naive expectation
that more corner draws should close corner-heavy bins sooner). This
build's `$urandom` is deterministically seeded (no explicit `$srandom`
call anywhere in this repo's examples), so both numbers are from one
fixed draw sequence each, not a statistical comparison across seeds --
the 252-vs-384 ordering should not be read as "1-in-4 is reliably
faster," only as "both closed well within budget in the one sequence
each rate actually produces here." Given that, the committed file kept
the established 1-in-4 rate (see
`examples/phase2/alu_manual_functional_coverage_sim_output_2026-08-26.txt`
for the committed run's actual numbers) for consistency with
`alu_manual_constrained_random.sv` rather than introducing an
unnecessary difference between the two files.

This process -- checking a generator-tuning hypothesis against real
coverage numbers before changing anything, and reporting the actual
result even when it didn't match the initial expectation -- is the
substantive point of doing coverage-driven closure at all, manual model
or not: the coverage report is what should decide whether the generator
needs to change, not intuition about which bins "should" be rare.

## References / prior context

- `notes/2026-08-25-oop-testbench-components.md` and
  `notes/2026-08-26-randomization-rand-randc-constraints.md` -- prior
  tooling-gap findings this session's investigation continues.
- IEEE 1800-2017 LRM, Chapter 19 (Functional coverage) -- standard
  reference for the coverpoint/cross/bins/option.at_least semantics in
  Section 1, independent of any tooling finding.

**WebSearch/WebFetch availability:** available this session; not used
for this note, since functional-coverage semantics are stable IEEE 1800
LRM / standard textbook material (consistent with this repo's approach
to comparable foundational content in every prior session), and the
tooling-gap findings came entirely from direct experimentation with the
installed Icarus Verilog 10.3, not from search.
