# Phase 1 Milestone: Synchronous FIFO Design + Directed Testbench

**Date:** 2026-08-23
**Roadmap item:** Phase 1 — Digital Logic & HDL Fundamentals
**Covers checklist item:** "Milestone: synchronous FIFO or FSM design +
directed testbench (Icarus Verilog + GTKWave)" — the last remaining
Phase 1 item.

This session resolved the tooling blocker noted in every prior Phase 1
session (2026-08-22, and earlier today): Icarus Verilog can be obtained
in this sandbox without root by downloading the Ubuntu 22.04 `.deb`
directly and extracting it with `dpkg-deb -x` (see
`tools/setup_iverilog.sh`, added earlier today). With a real simulator
available, this milestone was completed with genuine simulation evidence
rather than hand-derived expected behavior.

## Design

`examples/phase1_milestone/sync_fifo.v`: a parameterized (`WIDTH`,
`ADDR_WIDTH`), single-clock-domain synchronous FIFO using the standard
extra-pointer-bit technique to distinguish full from empty without a
separate counter (`wr_ptr`/`rd_ptr` are `ADDR_WIDTH+1` bits; the top bit
is a wrap-parity bit). Read is combinational/first-word-fall-through.
Deliberately scoped to a single clock domain — the gray-coded,
synchronizer-based async/CDC FIFO variant is explicitly Phase 6 material
("CDC verification basics" in the roadmap README) and is noted as a
natural extension of this exact module once that phase is reached.

Illegal-operation handling (`wr_en` while full, `rd_en` while empty) is
flagged with an explicit runtime `$error` check rather than silently
ignored. The idiomatic way to write this in SystemVerilog is an immediate
assertion (`assert (!full) else $error(...)`), but Icarus Verilog 10.3
(the version obtained this session) does not implement immediate
assertion statements (`sorry: Simple immediate assertion statements not
implemented`) — discovered by attempting it and reading the compiler
error, not assumed in advance. A plain `if` with `$error` was substituted
with equivalent semantic intent; revisiting with real `assert` syntax on
a simulator with full SVA support (a commercial tool, or a newer/
differently-built open-source simulator) is a good candidate for a future
Phase 5 (assertions/formal) session, since Phase 5 will need real SVA
support regardless.

## Testbench

`examples/phase1_milestone/sync_fifo_directed_tb.v`: directed,
self-checking, with an independent SystemVerilog queue
(`logic [WIDTH-1:0] ref_model[$]`) as the reference model — deliberately
a different underlying data structure from the DUT's fixed-size circular
buffer with wrapping pointers, so the reference model cannot share a
pointer-arithmetic bug with the DUT. Seven directed test phases:

1. Reset state (`empty=1`, `full=0` immediately after reset).
2. Fill to full (`DEPTH` pushes), checking `full` asserts at exactly the
   right push.
3. Illegal push while full — a deliberate protocol violation, checked to
   (a) trigger the DUT's `$error` and (b) leave both DUT and reference
   model state unchanged (write correctly dropped, not corrupted).
4. Drain to empty (`DEPTH` pops), checking FIFO ordering against the
   reference queue on every pop.
5. Illegal pop while empty — symmetric to (3).
6. Wrap-around stress: push 5, pop 3, push 6 more (crossing the 8-entry
   pointer wrap boundary), then drain fully — specifically exercises the
   modular pointer arithmetic rather than only the simple fill/drain
   case, which alone would not touch the wrap-around code path at all
   for a FIFO that is filled once and fully drained without interleaving.
7. Simultaneous push+pop on the same clock cycle, across 10 cycles from
   a partially-filled state — checks that both pointers can advance
   together in one cycle without interfering (a common design mistake is
   an off-by-one in the full/empty logic that only manifests when push
   and pop happen simultaneously right at the boundary).

## Results (real simulation, not hand-derived)

```
$ iverilog -g2012 -o sim sync_fifo.v sync_fifo_directed_tb.v
$ vvp sim
ERROR: sync_fifo.v:89: sync_fifo: wr_en asserted while full=1 at time 115000 -- write dropped, pointer not advanced (protocol violation, not a design feature)
ERROR: sync_fifo.v:108: sync_fifo: rd_en asserted while empty=1 at time 205000 -- read ignored, pointer not advanced (protocol violation, not a design feature)
---------------------------------------------------------
Total checks = 138, errors = 0
PASS: sync_fifo matched the reference model on every checked cycle across all 7 directed test phases.
```

Full captured output committed at
`examples/phase1_milestone/sync_fifo_sim_output_2026-08-23.txt`. The two
`$error` lines are the **expected**, deliberately-triggered protocol-
violation checks from test phases 3 and 5 above, not unexpected failures
— the testbench's own PASS/FAIL summary (138 checks, 0 errors) is the
actual correctness verdict, and it passed on the first debugged
compile+run (after fixing two Icarus-specific syntax issues described
below — the design and testbench logic itself was correct on the first
attempt that actually compiled).

A waveform dump (`examples/phase1_milestone/sync_fifo_wave.vcd`) is
generated via `$dumpfile`/`$dumpvars` and committed as evidence the dump
mechanism works end-to-end (817 lines, non-empty, contains real signal
transitions). GTKWave itself is not available in this automation
sandbox (no display/GUI), so the waveform has not been visually
inspected in this session — it is intended to be opened with
`gtkwave sync_fifo_wave.vcd` on a machine with GTKWave installed, per the
roadmap milestone's original "Icarus Verilog + GTKWave" framing.

## Debugging notes (useful for future sessions using this same toolchain)

Two Icarus-Verilog-10.3-specific issues were hit and fixed during this
session, worth recording so a future session does not need to
rediscover them:

1. Immediate assertion statements (`assert (...) else $error(...)`) are
   not implemented in this simulator version — use a plain
   `if (cond) $error(...)` instead.
2. SystemVerilog's `void'(expr)` void-cast syntax (commonly used to
   explicitly discard a function/method return value, e.g.
   `void'(queue.pop_front())`) caused a syntax error in this simulator
   version; assigning the return value to an otherwise-unused variable
   instead (`tmp = queue.pop_front();`) was used as a portable
   workaround.

Both were found by compiling, reading the actual Icarus error message,
and fixing accordingly — not assumed in advance.

## Progress

Marked the Phase 1 milestone done in `progress.md`. **All of Phase 1
(Digital Logic & HDL Fundamentals) is now complete.** Next session should
begin Phase 2 (SystemVerilog for Verification), starting with SV data
types and interfaces/modports per the roadmap README, and can reuse
`tools/setup_iverilog.sh` directly (Icarus Verilog 10.3 has reasonable,
if incomplete, SystemVerilog support — the two gaps above are the only
ones found so far, and Phase 2's OOP/randomization/coverage constructs
should be checked against this same simulator early rather than assumed
to work, given the gaps already found).

## References

Standard, stable FIFO-design and testbench-methodology content (the
extra-pointer-bit full/empty technique and directed self-checking
testbench structure are textbook material, e.g. Sutherland/Mills-style
Verilog references and standard verification textbooks already cited in
earlier sessions' notes) — written directly without WebSearch, consistent
with this repo's approach to stable foundational content. WebSearch was
available this session but was not used for this reason.
