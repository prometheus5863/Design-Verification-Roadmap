# SystemVerilog Data Types + Interfaces/Modports (Phase 2, Week 5)

**Date:** 2026-08-24. First Phase 2 study session (Phase 1 -- Digital Logic
& HDL Fundamentals -- is complete as of 2026-08-23). Covers the first
Phase 2 checklist item: "SV data types, interfaces/modports."

## 1. Why this is the right first Phase 2 topic

Phase 1 used plain Verilog-2001 throughout (bare `wire`/`reg`, individual
ports, `parameter`). Phase 2's job is to move to the constructs an actual
verification testbench is written in. Data types and interfaces are the
right starting point because everything later in Phase 2 (classes,
randomization, coverage, assertions) is built on top of them -- a
`rand` class member needs a real data type to be meaningful, and a
UVM-style agent's driver/monitor pair is exactly the interface/modport
pattern generalized into class-based components.

## 2. SystemVerilog data types relevant to verification

- **`logic`**: a 4-state (0/1/X/Z), single-driver type that replaces
  `wire`/`reg` in SV code. Unlike `reg`, `logic` can be driven by a
  continuous `assign` *or* a procedural block -- the compiler enforces
  single-driver rules regardless of which. This is why SV style boards
  use `logic` almost everywhere and reserve `wire` for genuinely
  multiply-driven nets (e.g. tri-state buses).
- **2-state types** (`bit`, `byte`, `int`, `shortint`, `longint`): no X/Z
  state, so they simulate faster and pack more predictably, but they
  silently coerce X/Z from a 4-state source to 0 -- exactly the wrong
  thing for RTL signals where X-propagation is a real bug-finding
  mechanism (an uninitialized or contended signal should read as X, not
  silently become 0). Rule of thumb used throughout this repo going
  forward: **RTL and DUT-facing signals stay 4-state (`logic`)**;
  2-state types are reserved for pure testbench bookkeeping (loop
  counters, scoreboard entries, coverage bins) where X/Z can't
  meaningfully occur.
- **Packed vs. unpacked arrays**: a packed array (`logic [7:0] a`) is
  stored as a contiguous bit vector and can be manipulated as a whole
  (arithmetic, comparison); an unpacked array (`logic a [0:7]` or
  `logic [7:0] mem [0:255]`) is a genuine array of elements and is what
  you reach for to model memories/register files or a testbench's
  transaction queue.
- **`enum`**: gives a restricted, named value set to what would
  otherwise be a bare vector -- catches typos (an out-of-range case is
  either flagged or hits a `default`), and makes waveforms/`$display`
  output vastly more readable than raw hex/binary codes. Used in this
  session's example for the ALU opcode (`alu_op_e`, see Section 4).
- **`struct` (packed)**: bundles related signals into one typed object.
  A *packed* struct additionally behaves like a single bit vector for
  waveform/VCD and comparison purposes, which matters when the struct is
  used as an interface field or a DUT output port, as in this session's
  `alu_flags_s` (zero/carry/overflow bundled instead of three loose
  wires).

## 3. Interfaces and modports

An `interface` groups a set of related signals (e.g. every wire between
a DUT and its testbench) into one named, reusable declaration, instead
of each module independently listing every one of those signals in its
own port list. A `modport` then gives each side of that interface a
*direction-checked* view: the DUT's modport marks the signals it reads
as inputs and the signals it drives as outputs; the testbench's modport
is the mirror image. On a simulator with full interface-port support,
if a testbench file accidentally tried to drive a signal its modport
marks as an input, that is a **compile-time** error -- not a silent
multi-driver contention bug that might only show up (or might not) at
simulation time. This single-point-of-definition property (one
interface declaration generates both sides' views, instead of two
independently hand-maintained port lists that can drift out of sync) is
the actual payoff, and it's also structurally what a UVM `virtual
interface` handle wraps when it's threaded through class-based driver/
monitor components in Phase 4.

## 4. Worked example: `alu_if` / `alu_dut` / `alu_if_tb`

`examples/phase2/alu_if_and_dut.sv` and `examples/phase2/alu_if_tb.sv`
implement an 8-bit, one-cycle-latency ALU (ADD/SUB/AND/OR/XOR) using:
- `alu_op_e`, a packed 3-bit enum for the opcode
- `alu_flags_s`, a packed struct bundling zero/carry/overflow
- `alu_if`, an interface bundling all ten DUT<->TB signals, with `dut`
  and `tb` modports giving each side its direction-checked view

Directed, self-checking testbench: 12 vectors covering every opcode plus
carry/overflow/zero corner cases (e.g. `0xFF + 0x01` -> carry+zero,
`0x7F + 0x01` -> signed overflow, `0x00 - 0x01` -> borrow). Independent
reference model re-derives expected result/flags from first principles
(not by re-reading the DUT's compute logic). **Actually compiled and run**
with Icarus Verilog 10.3 (via `tools/setup_iverilog.sh`): all 12 checks
pass (`examples/phase2/alu_if_sim_output_2026-08-24.txt`), plus a real,
non-empty VCD waveform dump (`examples/phase2/alu_if_wave.vcd`).

## 5. Real toolchain gaps found this session (Icarus Verilog 10.3)

This session hit substantially more Icarus 10.3 SystemVerilog gaps than
the two found on 2026-08-23 (`assert`, `void'(...)`). Each was isolated
with a minimal standalone repro (2-10 lines) before being worked around
in the example files, so these are confirmed real toolchain limits, not
bugs in the example code:

1. **Interfaces cannot be used as module ports at all**, in any syntax
   form (`alu_if.dut vif`, plain `alu_if vif`, ANSI or non-ANSI style) --
   confirmed with a 2-line minimal interface. The interface
   *declaration* (including modports) compiles fine standalone; only
   using it to type a port fails. Worked around by giving `alu_dut` a
   plain port list and connecting it to the interface instance via a
   named port map in the testbench (`.a(vif.a)`, etc.) -- this still
   exercises the interface as a real typed signal bundle, just not the
   interface-as-port idiom itself.
2. **`always_comb` and `always_ff` do not compile at all**, in any form,
   even fully standalone with no ports/types involved (3-4 line
   repros). Plain Verilog-2001-style `always @*` and
   `always @(posedge clk or negedge rst_n)` -- already this repo's Phase
   1 style -- work fine and were used instead.
3. **`unique case` does not compile**; plain `case` works.
4. **SV assignment-pattern syntax** (`'{default: 1'b0}`, `'0` fill)
   **does not compile** for a packed-struct target; per-field assignment
   (`flags.zero <= 1'b0;` etc.) works.
5. **Declaring an `enum`-typed variable inside a task or function scope
   crashes the compiler** with an internal assertion
   (`net_scope.cc:211: ... find_enumeration_for_name ... Assertion
   'cur_scope' failed. Aborted`) -- as a local variable *or* as a
   port/argument, `automatic` or not. Confirmed with a 6-line minimal
   repro. Packed-struct-typed locals/arguments do **not** trigger this.
   Worked around throughout `alu_if_tb.sv` by passing opcodes as plain
   `logic [2:0]` into every task/function and only ever using the real
   `alu_op_e` type at module (non-task/function) scope.
6. **Explicit enum casts** (`alu_op_e'(op_raw)`) as an assignment-RHS
   expression are rejected ("sorry: This cast operation is not yet
   supported"); a plain implicit assignment of the matching-width raw
   vector to the enum-typed signal (`vif.op <= op_raw;`) is accepted
   without complaint.
7. **`enum.name()`** is rejected with an explicit, non-crashing error
   ("sorry: Enumeration method name() is not currently supported in
   this context"); worked around with a small `case`-based lookup
   function for readable `$display` output.
8. **`%p` format specifier is unsupported** for `$display` (prints a
   literal `<%p>` and a runtime warning rather than the struct's value);
   worked around by printing the packed struct with `%b`/`%0d` instead.
9. **Functions cannot have `output`-direction arguments**
   ("Function arguments must be input ports."); the reference model
   (`ref_model`, which needs to return both a result and a flags struct)
   was written as a `task` instead of a `function`, consistent with how
   this repo's Phase 1 examples already used tasks for this purpose.

**Net assessment:** this Icarus 10.3 build's practical SystemVerilog
support is closer to "Verilog-2001 plus typedef enum/struct
declarations, `always @*`-style procedural blocks, and interface
*declarations* (but not interface *ports*)" than to full IEEE 1800-2017
support. This matters directly for the rest of Phase 2: classes,
randomization (`rand`/`constraint`/`randomize()`), and functional
coverage (`covergroup`/`coverpoint`) are all more advanced SV than
anything exercised today, and per the 2026-08-23 log's own prediction,
should be spot-checked against this simulator early rather than assumed
to compile. A newer Icarus build (or a different simulator entirely,
e.g. Verilator for lint/synthesis-style checking, though it does not
support behavioral testbench constructs like `initial`/`$display`
either) would likely resolve most of the above; this is now the
concrete list of what to re-test if/when one becomes available in this
sandbox.

## 6. Next session should

Continue Phase 2 with "OOP testbench components (transactions,
generators, drivers, monitors, scoreboards)" per progress.md. Given
finding 5 above (enum-in-task/function crash) and finding 9
(no function output arguments), class-based components should be
spot-checked incrementally rather than written in full before a first
compile attempt -- e.g. a `transaction` class with an `alu_op_e` field is
untested territory (class member declarations are a different scope
than task/function locals, so it may or may not hit the same crash) and
should be the very first thing tried.
