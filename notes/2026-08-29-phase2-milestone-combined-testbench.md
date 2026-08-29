# Study Notes: Phase 2 Milestone — Combined Constrained-Random + Coverage + Assertion-Style Testbench

**Date:** 2026-08-29
**Topic:** Phase 2 milestone (`progress.md`: "Milestone: constrained-random
SV testbench w/ scoreboard + coverage for a small DUT") — the last
unchecked Phase 2 item as of 2026-08-28, whose AUTOMATION_LOG.md entry
explicitly recommended integrating the three separate manual-workaround
examples built across 2026-08-26/2026-08-28 into one combined testbench,
rather than leaving them as three standalone demonstration files.

## 1. What this session did

Built `examples/phase2_milestone/alu_combined_tb.sv`, combining (in one
`initial` block driving one instance of the existing `alu_dut`):

- The transaction class, dist-like weighted opcode generator, and
  randc-like corner-value generator from
  `alu_manual_constrained_random.sv` (2026-08-26), unmodified.
- The coverpoint/cross bin-counting functional-coverage model and
  coverage-driven stopping criterion from
  `alu_manual_functional_coverage.sv` (2026-08-26, second session),
  unmodified.
- The scoreboard from `alu_manual_constrained_random.sv`
  (widened-add/subtract reference-model formulation), AND, run
  independently alongside it on every transaction, the assertion-style
  checker from `alu_sva_checker.sv` (magnitude-comparison reference-model
  formulation), unmodified in substance. Both checkers run on the same
  DUT output for every transaction; a mismatch would print from
  whichever caught it.

This is a deliberate methodological point, not redundancy: a real
verification environment layers a scoreboard (transaction-level,
typically reference-model-based) with concurrent assertions
(signal-level, invariant/protocol-based) specifically because the two
check different things in different ways, so a blind spot shared by one
formulation of "the obvious way to compute an ALU result" is unlikely to
be shared by a *different* formulation. Running both here, independently
formulated (as they already were in their separate source files, for
this exact reason per each file's own header), demonstrates that
principle concretely rather than only asserting it: if a bug had existed
in the DUT's own carry/overflow logic that happened to match one
reference-model style, the other (differently-formulated) check would
likely still have caught it.

## 2. Tooling status (re-confirmed, no new gaps found)

No new Icarus Verilog 10.3 tooling gaps were found while integrating
these three files — every SystemVerilog construct used below (classes
with tasks/functions, `task automatic` with `output` arguments,
module-level unpacked arrays for bin counters, `$urandom_range`,
`$sformatf`, `real` functions) had already been individually verified
working in its source file, and combining them into one module compiled
and ran cleanly on the first attempt with the pinned toolchain. This is
itself a useful (negative) finding: none of the three examples' working
patterns conflict with each other when combined in a single module scope
(e.g. the module-level bin-counter arrays from the coverage example and
the module-level corner-value array from the randomization example
coexist without incident).

**Environment note (secondary data point, not the basis for the
committed result):** this session's container again had root/`apt-get`
access (as 2026-08-28's did) and the distribution default pulled in
Icarus Verilog 12.0. Per this repo's established 2026-08-28 practice, the
pinned `tools/setup_iverilog.sh` build (confirmed via `iverilog -V` ->
10.3 stable) was used as the authoritative toolchain for the committed
result, for direct comparability with the existing tooling-gap corpus
(all of which is 10.3-based). As a secondary check, the same two-file
compile was also run against the apt-installed 12.0: it compiled without
error but **`vvp` segfaulted immediately** ("Segmentation fault", no
further output) rather than running the testbench. This was not
investigated further (out of scope for today's milestone goal, and the
pinned-10.3 path already gives a real, working, evidence-backed result)
but is recorded here as a genuine 12.0-vs-10.3 compatibility difference
worth knowing about if a future session encounters an apt-installed
12.0-only environment and this file (or a similarly-structured one)
mysteriously produces no simulation output at all.

## 3. Results

Compiled and run with the pinned Icarus Verilog 10.3
(`iverilog -g2012 -o sim examples/phase2/alu_if_and_dut.sv
examples/phase2_milestone/alu_combined_tb.sv && vvp sim`; full output
captured in
`examples/phase2_milestone/alu_combined_sim_output_2026-08-29.txt`):

- **Scoreboard:** 252 checks, 0 errors.
- **Assertion-style checker:** 253 checks run (252 real + 1 deliberate),
  252 passed; the one deliberate corrupted-expectation case correctly
  failed with the expected diagnostic, proving the checker actually
  fires rather than only ever passing (same idiom as every prior checker
  example in this repo, e.g. `sync_fifo_directed_tb.v`'s illegal-push/
  illegal-pop cases and `alu_sva_checker.sv`'s own deliberate-fail case).
- **Functional coverage:** all three coverage components (5-bin op
  coverpoint, 3-bin a_corner coverpoint, 15-bin cross) closed at 100%,
  reached after 252 transactions — closing at essentially the transaction
  count as the pure scoreboard checks (252), since coverage sampling
  happens on the same loop iterations as scoreboard/assertion checking.
- A real, non-empty VCD waveform was captured
  (`alu_combined_wave.vcd`, 11155 lines / ~87 KB) alongside the console
  output.
- Overall milestone verdict printed by the testbench itself: **PASS**.

## 4. Progress tracking

Marks the Phase 2 milestone ("constrained-random SV testbench w/
scoreboard + coverage for a small DUT") done in `progress.md`, with the
same explicit-caveat style used for every native-tooling-gap item in this
phase (constrained-random, functional coverage, and SVA are all
hand-implemented workarounds on this build, not native SV — stated
plainly rather than implied by a bare checkmark). **This completes Phase
2 (SystemVerilog for Verification).**

## 5. Next steps

Phase 3 (Verification Methodology Fundamentals) is next per the roadmap
README: layered testbench architecture, TLM basics, verification
planning, and directed-vs-constrained-random-vs-coverage-driven
trade-offs, culminating in a written verification plan for a moderately
complex DUT (the README suggests a simple APB/AHB-lite peripheral or a
UART) that becomes the spec for the Phase 4 UVM testbench. Unlike Phase
2's constructs, Phase 3's milestone deliverable is a planning document,
not simulator-dependent code — so tooling-gap risk is lower for that
specific deliverable, though any illustrative code snippets should still
be spot-checked against this build's established gap list before being
presented as running examples.
