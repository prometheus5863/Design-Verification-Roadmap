# OOP Testbench Components: Transaction, Generator, Scoreboard (Phase 2, Week 6)

**Date:** 2026-08-25. Covers the second Phase 2 checklist item: "OOP
testbench components (transactions, generators, drivers, monitors,
scoreboards)" -- the item `alu_if_tb.sv`'s own 2026-08-24 header comment
already flagged as "next." WebSearch was not used this session; this
topic (standard class-based testbench architecture) is core, stable
verification methodology rather than something needing current sources,
so well-established technical knowledge was used directly, cross-checked
against this repo's own hands-on toolchain experiments (Sections 2-3
below).

## 1. Why move to classes at all

A directed testbench (`alu_if_tb.sv`, 2026-08-24) hard-codes both *what*
stimulus to apply and *how* to apply/check it in one procedural block.
That does not scale: real DUTs need hundreds to thousands of stimulus
combinations, and hand-writing each one is both slow and a poor use of
simulation time (a human can only think of the corner cases they already
know to look for). The standard fix, going back to the OVM/VMM
methodologies that UVM later unified, is to split a testbench into
reusable objects with one job each:

- **Transaction**: one unit of stimulus (or observed behavior) as a data
  object -- for a simple ALU, one `(a, b, op)` triple; for a bus protocol,
  one packet/beat.
- **Generator** (a.k.a. sequencer in UVM): produces a stream of
  transactions, ideally with randomized field values so it can explore
  the input space far beyond what a human would hand-write.
- **Driver**: consumes transactions and pulses the DUT's actual pins to
  apply them, cycle-accurately.
- **Monitor**: passively samples DUT pins (never drives them) and
  reconstructs observed transactions -- both what went in and what came
  out.
- **Scoreboard**: an independent reference model that predicts expected
  behavior and compares it against what the monitor observed, tracking
  pass/fail state over the whole run.

The payoff: swapping in a different generator (directed -> random ->
coverage-driven) or a different DUT (different driver/monitor pin
mapping) doesn't require touching the scoreboard's checking logic, and
vice versa -- each piece can be developed, debugged, and reused
independently. This is also exactly the reusability UVM's base classes
(`uvm_sequence`, `uvm_driver`, `uvm_monitor`, `uvm_scoreboard`) are built
to standardize, so getting comfortable with the plain-SV-class version of
this split now is directly preparatory for Phase 4.

References: Sutherland & Spear, *SystemVerilog for Verification*, 3rd
ed. (Springer, 2017), chs. 9-10 (classes; testbench architecture);
ChipVerify, "SystemVerilog Testbench" and "SystemVerilog Classes"
tutorial pages (chipverify.com/systemverilog); Cummings & Sutherland
(Sunburst Design/SNUG papers) on layered testbench structure -- the same
sources already used for this repo's Verilog/SV coding-style notes
(2026-08-22, 2026-08-23).

## 2. Communication between components: the mailbox problem

The idiomatic channel between a generator and a driver (or a monitor and
a scoreboard) is a `mailbox` -- a built-in thread-safe FIFO class every
SV simulator is supposed to provide, so a generator can `put()`
transactions as fast or slow as it likes and a driver `get()`s them on
its own clock-synchronized schedule, decoupling their timing entirely.

This session found, with a minimal standalone repro, that **the Icarus
Verilog 10.3 build this repo's `tools/setup_iverilog.sh` installs does
not implement `mailbox` at all** -- neither the parameterized form
(`mailbox #(int) mbx;`) nor the plain form (`mailbox mbx;`) parses.
`semaphore` (the other standard built-in synchronization class) was not
separately tested but is expected to fail identically, since neither is
a user-definable SV construct -- both are library classes the simulator
itself has to provide, and this build simply doesn't.

Practical consequence for this session's example
(`examples/phase2/alu_oop_tb_components.sv`): the generator/scoreboard
communicate by having the generator hand back one transaction at a time
via an `output` argument (confirmed to work -- see Section 3), with its
fields immediately unpacked to plain scalars in the calling code, rather
than by decoupled `put()`/`get()` calls through a mailbox. This is a
real architectural simplification forced by the tool, not a stylistic
choice -- worth remembering when reading a real UVM testbench later,
where `uvm_analysis_port`/`uvm_tlm_fifo` (mailbox-like TLM channels under
the hood) are used pervasively for exactly this decoupling.

## 3. Class-handle plumbing: what actually works on this Icarus build

Because of the mailbox gap, this session needed to work out from first
principles what *does* work for getting a class object's data from one
task to another on this specific toolchain, since none of the existing
examples in this repo had exercised classes calling into other classes'
tasks before. Minimal repros (kept as scratch files, not committed --
the working conclusions are captured here and in the example file's
header) established:

| Construct | Works? |
|---|---|
| `task foo(output some_class_type h);` -- class handle as `output` arg | Yes |
| `task foo(input some_class_type h);` -- class handle as `input` arg | **No** -- "sorry: I do not know how to elaborate r-value as IVL_VT_CLASS" |
| `function some_class_type foo();` -- class handle as a function return value | **No** -- same error as above |
| `task foo(ref <any type> x);` -- `ref` argument, any type | **No** -- "sorry: Reference ports not supported yet." |
| `task foo(output <plain type> x);` -- plain-typed `output` arg | Yes |
| `virtual some_interface vif;` as a class member | **No** -- "invalid class item" |
| `some_class_type q[$];` then `q.push_back(h)` -- queue of class handles | **No** -- crashes the compiler (internal error + assertion failure) |
| `some_class_type arr[N];` or `arr = new[N]` -- array of class handles, variable-indexed | **No** -- "Scope index expression is not constant" (works fine for *literal* indices only) |
| `int q[$];` -- queue of a built-in scalar type | Yes |
| `n++` on a class member field, called repeatedly across separate task calls | **Silently wrong** -- gives the wrong accumulated total with no error (confirmed: 5 calls to a `bump(); n++;` task left the member at 1, not 5) |
| `n = n + 1;` on a class member field, same calling pattern | Yes -- correct every time |
| `$sformatf(...)` | **No** -- "System task/function $sformatf() is not defined by any module" |
| `{"a", "b"}` string concatenation | Yes |
| `class checker; ... endclass` | **No** -- `checker` is a reserved word on this build (IEEE 1800 `checker` construct), even though `checker` bodies aren't implemented; any other name works |

The `virtual <interface>`-as-class-member gap (row 6) is the single
most consequential one: it is the actual language mechanism a real SV/
UVM driver or monitor class uses to reach a DUT's pins from inside a
class method, so on this Icarus build a driver/monitor genuinely
*cannot* be written as a class that drives a DUT directly -- not a style
preference, a hard tool ceiling. Combined with the class-handle
`input`/return-value gap (rows 2-3) and the container-of-handles gap
(rows 7-8), a real polymorphic, decoupled UVM-style component graph is
out of reach on this specific build. The `n++` finding (row 9) is
separately the most dangerous of the session's findings precisely
*because* it produces no error -- a scoreboard using `errors++` would
silently under-report failures with no diagnostic at all.

## 4. What was actually built given these constraints

`examples/phase2/alu_oop_tb_components.sv` (reusing `alu_dut` from
`alu_if_and_dut.sv` unmodified as the DUT-under-verification) implements:

- `alu_transaction`: a real class encapsulating one ALU stimulus item
  (`a`, `b`, `op_raw` fields), with a `randomize_fields()` method (manual
  `$urandom_range`-based -- constrained-random `randomize()` is a
  separate, still-open finding; see the note in Section 5) and an
  `op_name()` helper for readable output.
- `alu_generator`: a real class with persistent state (`num_generated`)
  and a `next_transaction(output alu_transaction t)` task, the one
  direction class handles reliably cross a task boundary on this build.
- `alu_scoreboard`: a real class with persistent `checks`/`errors`
  counters, an independent `predict()` reference-model task (deliberately
  re-derives expected result/flags from first principles, mirroring
  `alu_if_tb.sv`'s `ref_model` task rather than reusing `alu_dut`'s own
  logic), and a `check()` task that compares actual vs. predicted and
  updates its counters using the explicit `x = x + 1` form (per the
  `n++` finding above).
- Driver/monitor roles remain plain procedural code in the top-level
  `initial` block (as in `alu_if_tb.sv`), immediately after each
  `next_transaction()` call, because the virtual-interface-in-class gap
  (Section 3) rules out writing them as classes at all on this build.

Run with 12 pseudo-randomly generated transactions
(`examples/phase2/alu_oop_tb_sim_output_2026-08-25.txt`): all 12 passed
against the scoreboard's independent reference model, and the negative
path (does the scoreboard actually *catch* a wrong result rather than
always passing) was separately verified with a throwaway deliberately-
wrong-actual-value repro before being discarded, to be confident the
`PASS`/`0 errors` result above reflects a working check and not a
scoreboard that can't fail.

## 5. Open items for the next two Phase 2 milestones

- **Randomization** (`rand`/`randc`, constraints, `randomize()`,
  `dist`): `randomize()` itself was briefly probed this session (not the
  focus, but encountered while testing `rand` fields) and does not
  appear to be implemented on this Icarus 10.3 build either --
  `p.randomize()` and `void'(p.randomize())` both failed to elaborate
  ("No function named `p.randomize' found in this context"). This
  should be confirmed properly (minimal repro, both forms, plus
  `randc` and a simple `constraint` block) at the start of that
  milestone rather than assumed, exactly as this session did for OOP
  components.
- **Functional coverage** (`covergroup`/`coverpoint`/`cross`): not yet
  tested at all; given the pattern in Sections 2-3, this should also be
  spot-checked with a minimal repro before committing to a design for
  that milestone's example.
- **Phase 4 (UVM)**: per Section 3, this Icarus 10.3 build cannot run
  actual UVM (which depends on virtual interfaces, TLM/analysis-port
  channels, and polymorphic handle containers all at once). A different
  simulator will be needed by then -- Verilator has more complete SV
  class support in recent versions but has its own gaps, and a
  student/free tier of a commercial simulator (Questa, VCS, Xcelium) is
  the most realistic path to a fully spec-compliant UVM environment.
  Flagging this now, two phases early, rather than discovering it
  mid-Phase-4.

## References

1. Sutherland, C. & Spear, C. *SystemVerilog for Verification: A Guide
   to Learning the Testbench Language Features*, 3rd ed. Springer, 2017.
   Chs. 9-10.
2. ChipVerify. "SystemVerilog Classes" and "SystemVerilog Testbench."
   https://www.chipverify.com/systemverilog/systemverilog-classes
3. Cummings, C. & Mills, D. (Sunburst Design). SNUG papers on
   layered/OOP testbench architecture (background for the generator/
   driver/monitor/scoreboard split later formalized in OVM/UVM).
4. IEEE 1800-2017 (SystemVerilog LRM) -- `mailbox`, `semaphore`,
   `virtual interface`, and class-handle argument-passing semantics
   (Sections 15.4, 15.5, 8.25, 25.x), used as the specification baseline
   for identifying which Icarus 10.3 behaviors above are non-conformant
   gaps vs. legitimate SV semantics.
5. This repo, `examples/phase2/alu_if_and_dut.sv` and `alu_if_tb.sv`
   (2026-08-24) -- prior tooling-limitation findings this session builds
   on directly.
