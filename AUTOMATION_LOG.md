# Automation Log

Dated log of automated study/work sessions on this roadmap repo. Each
session reads this file plus `progress.md` to determine what to work on
next, since sessions have no memory of each other.

---

## 2026-08-21 — Initial setup

**Status:** First automation run. Repo was empty (no commits, no branches).

**Work done:**
- Wrote `README.md`: a structured 6-phase, ~28-week self-study roadmap
  covering digital logic & HDL fundamentals, SystemVerilog for
  verification, verification methodology fundamentals, UVM, assertions &
  formal verification, and a capstone project (UVM environment for a
  register-mapped peripheral with interrupt + FIFO datapath). Each phase
  lists concrete topics, resources (textbooks, official docs, free
  tutorials/tools), and a milestone deliverable.
- Wrote `progress.md`: a checklist mirroring the roadmap phases/milestones,
  all currently unstarted.
- Wrote this `AUTOMATION_LOG.md`.
- Initialized the repo on `main` and made the first commit (repo had no
  prior commits/branches).

**Web search availability:** WebSearch tool was available this session,
but was not used for this particular initialization pass — the roadmap
content (standard digital design / SystemVerilog / UVM / formal
verification curriculum, canonical textbooks: Harris & Harris, Bergeron,
Spear, Salemi, Foster et al., and standard free resources: ASIC World,
ChipVerify, ChipVerify UVM tutorials, ChipVerify.com, Accellera UVM docs,
SymbiYosys docs) is drawn from well-established, stable industry/academic
knowledge rather than time-sensitive information, so it was written
directly. Future sessions covering specific topics (e.g. a particular UVM
feature or a specific tool's current docs) should use WebSearch where a
current primary source strengthens the notes.

**Next run should:** start Phase 1 (Digital Logic & HDL Fundamentals) —
write real study notes on Verilog blocking vs. non-blocking assignment
semantics (a foundational, commonly-misunderstood topic) and/or begin the
Phase 1 milestone deliverable (a small synchronous FIFO or FSM design
with a directed testbench in Icarus Verilog). Update `progress.md`
accordingly.

**Commits this run:** 1 (initial repo setup: README + progress.md +
AUTOMATION_LOG.md).

---

## 2026-08-22 — Phase 1 begins

**Status:** Second automation run. Repo state at start: README (6-phase
roadmap), progress.md (all Phase 1 items unstarted), AUTOMATION_LOG.md
from the 2026-08-21 initialization run. No `notes/` or `examples/`
directories existed yet.

**Work done:**

1. **Study notes**
   (`notes/2026-08-22-combinational-and-sequential-logic-review.md`):
   Verification-engineer-oriented review of Boolean algebra identities
   (De Morgan, absorption, consensus, XOR/XNOR), mux/demux/encoder/
   decoder/ALU structure (including the carry-out-vs-signed-overflow
   distinction, a common ALU-checker bug), latches vs. edge-triggered
   flip-flops, Moore vs. Mealy FSMs, state-encoding trade-offs (binary /
   one-hot / gray), illegal-state recovery, and setup/hold timing basics
   framed around why each topic matters for functional verification
   specifically (checkable properties, ambiguity in spec language,
   corner-case coverage), not just design. Marked "Combinational logic
   review" and "Sequential logic review" done in `progress.md`.

2. **Study notes + code**
   (`notes/2026-08-22-verilog-fundamentals-blocking-vs-nonblocking.md`,
   `examples/phase1/shift_register_blocking_vs_nonblocking.v`): Verilog-
   2001 module/port syntax, combinational vs. sequential `always` block
   conventions, and a detailed IEEE 1364 event-scheduling explanation of
   blocking vs. non-blocking assignment semantics (2-stage shift register
   and register-swap examples, plus the failure mode when the two are
   swapped -- collapsed shift-register delay / broken swap). Companion
   Verilog file has a correct (non-blocking) and a deliberately buggy
   (blocking) version of the same shift register plus a directed,
   self-checking testbench with a software reference model. **Not
   simulated in this session** -- Icarus Verilog is not installed in this
   sandbox and there is no package-manager write access to install it
   (`apt-get install`/`apt-get download` both fail with permission/lock
   errors; no conda/pip-installable alternative found). This is flagged
   explicitly in the file header and notes rather than presented as
   simulated; expected behavior is derived from careful manual
   application of the standard semantics, which is unambiguous for the
   examples chosen. Running it locally with `iverilog`/`vvp` is a natural
   follow-up. Marked "Verilog-2001 fundamentals" done in `progress.md`.

**Web search availability:** WebSearch was available this session but was
not used for either note, since Phase 1 digital-logic and Verilog
event-scheduling semantics are stable, standard content (IEEE 1364 LRM,
standard textbook material) rather than time-sensitive information.

**Next run should:** continue Phase 1 with "Synthesizable coding style +
simple self-checking testbenches" (a natural extension of today's
testbench, generalizing the self-checking pattern used above), then the
Phase 1 milestone deliverable (a synchronous FIFO or FSM design with a
directed testbench) -- ideally on a session where `iverilog` is available
so the milestone testbench can actually be run and its pass/fail output
committed as real evidence, not just claimed. If iverilog remains
unavailable, consider writing the FIFO/FSM RTL and testbench with
expected-output analysis documented by hand (as done today), and note the
same tooling limitation.

**Commits this run:** 2 (combinational/sequential logic review notes,
Verilog fundamentals + blocking/non-blocking notes and code).

---

## 2026-08-23 — Phase 1 complete; tooling blocker resolved

**Status:** Third automation run. Repo state at start: README (6-phase
roadmap), progress.md (Phase 1's first 3 items done, "Synthesizable
coding style..." and the Phase 1 milestone still unstarted),
AUTOMATION_LOG.md through 2026-08-22. Every prior session had flagged
the same tooling blocker: no Icarus Verilog available, no root/apt
access to install it.

**Work done:**

1. **Tooling blocker resolved.** Found that Icarus Verilog's Ubuntu
   22.04 ("jammy") `.deb` package can be downloaded directly from the
   public Ubuntu archive and extracted with `dpkg-deb -x`, which only
   unpacks files and does not require install/root privileges (unlike
   `apt-get install`, which fails on a dpkg lock permission error in
   this sandbox). The extracted `iverilog`/`vvp` binaries need `-B`/`-M`
   flags pointing at the extracted (non-standard-path) helper-library
   directory. Scripted as `tools/setup_iverilog.sh` for future sessions
   to reuse without rediscovering this. Verified working: Icarus
   Verilog 10.3.

2. **Study notes + code**
   (`notes/2026-08-23-synthesizable-coding-style-and-self-checking-testbenches.md`,
   `examples/phase1/priority_encoder_style_and_testbench.v`): Covers the
   practical synthesis/simulation-mismatch checklist (incomplete
   sensitivity lists, latch inference from incomplete case/if coverage,
   mixed blocking/non-blocking, RTL delays, multi-driver signals,
   combinational feedback, reset style consistency) and the
   self-checking testbench pattern (independent reference model,
   reusable stimulus tasks, error-counting checker). Companion example:
   a clean vs. deliberately-buggy (missing-case, latch-inferring)
   priority encoder with an exhaustive 16-vector self-checking
   testbench. **Actually compiled and run** this session (using the
   newly-working Icarus Verilog) — both the clean and buggy variants
   behaved exactly as predicted; captured output committed
   (`examples/phase1/priority_encoder_sim_output_2026-08-23.txt`). Also
   retroactively compiled and ran the 2026-08-22 shift-register example,
   which that session could not simulate — it also matched its
   previously hand-derived expected behavior exactly
   (`examples/phase1/shift_register_sim_output_2026-08-23.txt`). Marked
   "Synthesizable coding style + simple self-checking testbenches" done
   in `progress.md`.

3. **Phase 1 milestone completed**
   (`examples/phase1_milestone/sync_fifo.v`,
   `sync_fifo_directed_tb.v`): parameterized single-clock synchronous
   FIFO (extra-pointer-bit full/empty technique, first-word-fall-through
   read) with a directed, self-checking testbench (independent
   SystemVerilog-queue reference model, 7 test phases: reset,
   fill-to-full, illegal-push-while-full, drain-to-empty with ordering
   check, illegal-pop-while-empty, wrap-around stress, simultaneous
   push+pop). Compiled and run with Icarus Verilog 10.3: **138 checks, 0
   errors**, all phases pass. Captured console output and a real,
   non-empty VCD waveform dump both committed as evidence
   (`sync_fifo_sim_output_2026-08-23.txt`, `sync_fifo_wave.vcd` — GTKWave
   itself is not available in this sandbox, so the waveform has not been
   visually inspected, only confirmed to be a real, populated dump).
   Two Icarus-10.3-specific language-support gaps were hit and worked
   around (no immediate `assert` statement support; `void'(...)` cast
   syntax not accepted) and documented for future sessions. Marked the
   Phase 1 milestone done in `progress.md`.

**Phase 1 (Digital Logic & HDL Fundamentals) is now fully complete.**

**Web search availability:** WebSearch was available this session but
was not used, since all of today's content (synthesizable-style
conventions, FIFO design technique, self-checking testbench structure)
is stable, standard digital-design/verification knowledge rather than
time-sensitive information — consistent with the previous two sessions'
approach to comparable foundational content.

**Next run should:** begin Phase 2 (SystemVerilog for Verification),
starting with SV data types and interfaces/modports per the roadmap
README. `tools/setup_iverilog.sh` should be reused directly rather than
re-solved. Icarus Verilog 10.3's SystemVerilog support is reasonable but
incomplete (see the two gaps found and documented today) — Phase 2's
OOP/randomization/functional-coverage constructs are more advanced
SystemVerilog than anything exercised so far, and should be spot-checked
against this simulator early in that work rather than assumed to
compile, given the gaps already found in even fairly basic constructs.

**Commits this run:** 5 (synthesizable-style notes + example + sim
evidence + tools/setup_iverilog.sh, progress.md update for that item,
Phase 1 milestone FIFO design + testbench + sim evidence + waveform, this
AUTOMATION_LOG.md update).

---

## 2026-08-24 — Phase 2 begins: SV data types + interfaces/modports

**Status:** Fourth automation run. Repo state at start: Phase 1 fully
complete (per 2026-08-23), Phase 2 not yet started, `tools/
setup_iverilog.sh` working (Icarus Verilog 10.3).

**Work done:**

1. **Study notes**
   (`notes/2026-08-24-systemverilog-data-types-interfaces-modports.md`):
   Covers SV data types relevant to verification (`logic` vs. 2-state
   types and why RTL/DUT signals should stay 4-state, packed vs.
   unpacked arrays, `enum`, packed `struct`) and the interface/modport
   connection idiom (single point of definition for both sides' views,
   direction-checked at compile time -- the reason to use one at all,
   and the same pattern a UVM virtual interface wraps in Phase 4).

2. **Code + results** (`examples/phase2/alu_if_and_dut.sv`,
   `examples/phase2/alu_if_tb.sv`,
   `examples/phase2/alu_if_sim_output_2026-08-24.txt`,
   `examples/phase2/alu_if_wave.vcd`): An 8-bit, one-cycle-latency ALU
   (ADD/SUB/AND/OR/XOR) using a packed enum opcode (`alu_op_e`), a packed
   struct for status flags (`alu_flags_s`), and an `alu_if` interface
   with `dut`/`tb` modports. Directed, self-checking testbench: 12
   vectors covering every opcode plus carry/overflow/zero corner cases,
   with an independent reference model. **Actually compiled and run**
   with Icarus Verilog 10.3: all 12 checks pass; a real, non-empty VCD
   waveform was also captured.

   Getting this to compile surfaced substantially more Icarus 10.3 SV
   gaps than the two found on 2026-08-23, each confirmed with a minimal
   standalone repro before being worked around (full detail and repro
   descriptions in today's notes file, Section 5): interfaces cannot be
   used as module ports in any syntax form; `always_comb`/`always_ff`/
   `unique case` do not compile at all (plain `always @*`/
   `always @(posedge ... or negedge ...)`/`case` -- already this repo's
   Phase 1 style -- were used instead); SV assignment-pattern syntax
   (`'{default: ...}`) does not compile for a struct target; declaring
   an enum-typed variable inside a task or function scope (as a local or
   an argument) crashes the compiler with an internal assertion
   (packed-struct locals/arguments do not trigger this); explicit enum
   casts and `enum.name()` are both rejected; `%p` is an unsupported
   `$display` format; and functions cannot have `output` arguments
   (worked around by using a `task` for the reference model instead, as
   Phase 1 already did). Net assessment recorded in the notes: this
   Icarus 10.3 build's practical SV support is closer to "Verilog-2001
   plus typedef enum/struct declarations and always @* procedural
   blocks" than to full IEEE 1800-2017 support -- directly relevant
   heading into classes/randomization/coverage, which are all more
   advanced SV than anything exercised today.

3. **Progress tracking**: marked "SV data types, interfaces/modports"
   done in `progress.md`.

**Web search availability:** WebSearch was available this session but
was not used, since today's content (SV data type semantics, interface/
modport syntax and rationale, IEEE 1800 LRM behavior) is stable,
standard language-reference material rather than time-sensitive
information, consistent with prior sessions' approach to comparable
foundational content. All of today's *tooling-gap* findings (Section 5
of the notes) came from direct experimentation with the installed
Icarus Verilog 10.3, not from search.

**Next run should:** continue Phase 2 with "OOP testbench components
(transactions, generators, drivers, monitors, scoreboards)." Given the
enum-in-task/function crash and the no-function-output-arguments gap
found today, class member declarations are untested territory and
should be spot-checked with a minimal repro (e.g. a `transaction` class
with a single `alu_op_e`-typed field) before writing a full class
hierarchy, exactly as today's session did before committing to the
interface/modport design.

**Commits this run:** 3 (SV data types + interfaces/modports study
notes, alu_if example code + compiled/simulated evidence, progress.md
update; this AUTOMATION_LOG.md update commit makes 4).

---

## 2026-08-25

**Status:** Fifth automation run.

**Repo state at start:** Phase 1 complete; Phase 2's first item ("SV
data types, interfaces/modports") complete as of 2026-08-24, with that
session's own notes flagging "OOP testbench components
(generator/driver/monitor/scoreboard as separate class objects)" as the
next item -- exactly matching `progress.md`'s next unchecked box, so
that was today's target.

**Work done:**

1. **Tooling investigation + code**
   (`examples/phase2/alu_oop_tb_components.sv`,
   `examples/phase2/alu_oop_tb_sim_output_2026-08-25.txt`,
   `examples/phase2/alu_oop_tb_wave.vcd`): Before writing the full
   example, ran ~10 minimal standalone repros against the installed
   Icarus Verilog 10.3 build to find out which class-related SV
   constructs a generator/scoreboard testbench would actually need
   (classes calling into other classes' tasks had not been exercised by
   any prior example in this repo). Found: `mailbox`/`semaphore` are not
   implemented at all; a class cannot hold a `virtual <interface>`
   member (the exact mechanism a real driver/monitor class needs to
   reach DUT pins); a class handle can be returned via a task's `output`
   argument but NOT as an `input` argument or a function return value;
   `ref` arguments fail outright; queues/arrays of class-handle type
   crash or reject variable indexing (built-in-scalar-type queues work
   fine); `$sformatf()` is unimplemented; `checker` is a reserved
   identifier; and, most dangerously, `n++` on a class member field
   silently under-accumulates across repeated calls with no error,
   while `n = n + 1` works correctly. Designed the example around these
   confirmed-working constructs rather than discovering the gaps
   mid-file: `alu_transaction` (stimulus encapsulation + manual
   `$urandom_range`-based fill), `alu_generator` (hands back one
   transaction at a time via an `output` arg), `alu_scoreboard`
   (independent reference model + persistent checks/errors counters
   using the explicit-increment form). Driver/monitor stayed procedural
   given the virtual-interface gap. Compiled and ran against the
   existing `alu_dut` (reused unmodified from `alu_if_and_dut.sv`): 12
   pseudo-random transactions, 12/12 passed against the scoreboard's own
   model; separately verified with a throwaway negative-path repro that
   the scoreboard actually flags a wrong result rather than always
   passing, before discarding that repro.

2. **Study notes**
   (`notes/2026-08-25-oop-testbench-components.md`): Covers the standard
   transaction/generator/driver/monitor/scoreboard architecture and why
   it replaces a monolithic directed testbench (Sutherland & Spear ch.
   9-10; ChipVerify; Sunburst Design/SNUG background -- same source
   family as prior sessions), then documents the full tooling
   investigation from item 1 as a reference table, and flags two
   forward-looking risks: `randomize()` itself also appears unsupported
   on this build (briefly probed, not the focus this session -- needs a
   proper confirming repro at the start of the Randomization milestone),
   and full UVM (Phase 4) will need a different simulator entirely given
   how many of today's gaps (virtual interfaces, TLM-like channels,
   polymorphic handle containers) UVM's base classes depend on
   simultaneously.

3. **Progress tracking**: marked "OOP testbench components (transactions,
   generators, drivers, monitors, scoreboards)" done in `progress.md`.

**Web search availability:** WebSearch was available this session but
was not used for the methodology background (transaction/generator/
driver/monitor/scoreboard architecture is stable, standard verification
knowledge), consistent with prior sessions' approach to comparable
foundational content. All of today's tooling-gap findings came from
direct experimentation with the installed Icarus Verilog 10.3, not from
search.

**Next run should:** continue Phase 2 with "Randomization (`rand`/
`randc`, constraints, `randomize()`, `dist`)." Given today's finding
that plain `randomize()` calls already failed to elaborate in passing,
the next session should open with a proper, dedicated set of minimal
repros (a `rand` field, a `constraint` block, `randomize()`,
`randomize() with {...}`, and `randc`) before designing that milestone's
example, exactly as today's session did for OOP components.

**Commits this run:** 3 (OOP testbench example code + compiled/simulated
evidence, study notes, progress.md update; this AUTOMATION_LOG.md update
commit makes 4).
