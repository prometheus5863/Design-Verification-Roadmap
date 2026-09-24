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

---

## 2026-08-26

**Status:** Sixth automation run.

**Repo state at start:** Phase 1 complete; Phase 2's first two items (SV
data types/interfaces, OOP testbench components) complete as of
2026-08-24/25. 2026-08-25's notes flagged that a quick probe suggested
`randomize()` might not elaborate on this Icarus Verilog 10.3 build, and
recommended opening today's session with a dedicated set of minimal
repros before designing the milestone example -- exactly what this
session did.

**Work done:**

1. **Tooling investigation + study notes**
   (`notes/2026-08-26-randomization-rand-randc-constraints.md`): Ran a
   dedicated set of minimal repros (kept in `/tmp/repro/`, not committed)
   covering `rand`/`randc` field declarations, `constraint` blocks,
   `inside`, `randomize()`, `randomize() with {...}`, and `dist`.
   **Confirmed decisively: this Icarus Verilog 10.3 build has no
   constrained-random support at all** -- `randomize()` is not
   implemented for any class ("No function named `f.randomize' found in
   this context" at elaboration), and `constraint`/`inside`/`dist` are
   all explicitly rejected by the parser ("sorry: ... not supported
   yet"). `rand`/`randc` field *declarations* parse fine on their own --
   it is specifically the solver/method machinery that is absent. This
   resolves 2026-08-25's open suspicion and is a materially bigger gap
   than any found on 2026-08-23/24/25 (those had usable in-language
   workarounds; this one does not -- native constrained-random simply
   isn't present on this build). Also documents standard SV
   randomization concepts (rand/randc semantics, constraint combination,
   randomize() with, dist weighting) independent of the tooling finding.
   WebSearch was available but not used, since this content is stable
   IEEE 1800 LRM / standard textbook material, consistent with prior
   sessions' approach; all tooling-gap findings came from direct
   experimentation.

2. **Two further, previously-undocumented tooling gaps found while
   building today's example** (added to the notes file, Section 2):
   inline class-instance declaration+construction (`Foo f = new();`)
   does not parse (the two-statement `Foo f; f = new();` form -- already
   used everywhere in this repo, it turns out by necessity -- works);
   and calling a function whose return value is discarded ("called as a
   task") from *within* another class task/function crashes the
   elaborator, though the identical call works fine from a top-level
   `initial` block. A third gap, found and worked around while
   implementing the example itself (documented in the example file's own
   header rather than the notes file, since it's implementation-specific
   to today's code): unpacked fixed-size arrays as **class properties**
   are fundamentally broken on this build (both assignment from within a
   class method and external indexing crash with different assertions),
   and SV queues inside classes are explicitly unsupported -- worked
   around by moving the randc-like corner-value queue to module-level
   (non-class) storage, which works fine (already proven safe by
   `sync_fifo.v`'s memory array).

3. **Code + results**
   (`examples/phase2/alu_manual_constrained_random.sv`,
   `alu_manual_constrained_random_sim_output_2026-08-26.txt`,
   `alu_manual_constrained_random_wave.vcd`): Since native
   `randomize()`/`constraint` are unavailable, built a hand-written
   equivalent demonstrating the same concepts against the existing
   `alu_dut` (reused unmodified): a manual `dist`-like weighted opcode
   picker (cumulative-weight table + single `$urandom_range` draw,
   biasing ALU_SUB to ~3/7 weight vs. uniform 1/5, since SUB's
   borrow/overflow logic is the ALU's most bug-prone corner per the
   2026-08-22 notes) and a manual `randc`-like corner-value queue
   (Fisher-Yates shuffle + pointer over the 5 classic 8-bit boundary
   values 0x00/0xFF/0x80/0x7F/0x01, guaranteeing each appears exactly
   once per cycle by construction, applied to the `a` operand every 4th
   transaction). Reused the existing scoreboard pattern unmodified for
   checking. **Actually compiled and run** with Icarus Verilog 10.3: 20
   transactions, 20/20 checks passed; op_raw histogram confirmed the
   dist-like bias (SUB=13/20 vs. uniform ~4/20); corner-value coverage
   confirmed the randc-like guarantee (all 5 corners hit exactly once
   across the 5 corner-draw slots in 20 transactions). Real, non-empty
   VCD waveform captured and committed alongside the console output.

4. **Progress tracking**: marked "Randomization (rand/randc, constraints,
   randomize(), dist)" done in `progress.md`, with an explicit caveat
   noting the native-tooling gap and the workaround used, rather than a
   bare checkmark that would misleadingly imply real constraint-solver
   experience was exercised.

**Next run should:** continue Phase 2 with "Functional coverage
(`covergroup`/`coverpoint`/`cross`)." Given today's pattern of finding
new gaps specifically when a construct is combined with classes (arrays,
inline construction, nested void calls), the next session should open
with minimal repros of `covergroup` both as a class member and at module
level before committing to a design -- `covergroup`/`coverpoint`/`cross`
are unexercised by anything in this repo so far and, like `randomize()`,
could plausibly be entirely unimplemented on this build rather than
partially supported; that should be established with a repro in the
first few minutes of that session rather than assumed either way.

**Commits this run:** 4 (randomization study notes + tooling-gap
findings, manual constrained-random ALU example + compiled/simulated
evidence, progress.md update, this AUTOMATION_LOG.md update commit
makes 4).

---

## 2026-08-26 (second session)

**Status:** Seventh automation run. See the graphene thesis repo's
AUTOMATION_LOG.md (2026-08-26, second session entry) for the same
dating note: the previous "## 2026-08-26" entry above was actually
written the evening before in UTC terms (host clock is IST); this
session genuinely started ~14 hours later at 2026-08-26 17:38 UTC.

**Repo state at start:** Phase 1 complete; Phase 2's first three items
(SV data types/interfaces, OOP testbench components, randomization) done
as of 2026-08-24/25/26-first-session. `progress.md`'s next unchecked item:
"Functional coverage (`covergroup`/`coverpoint`/`cross`)." The
2026-08-26 first-session notes explicitly recommended opening this
session with minimal `covergroup` repros before designing an example,
given the possibility it could be entirely unimplemented like
`randomize()` turned out to be -- exactly what this session did.

**Work done:**

1. **Tooling investigation + study notes**
   (`notes/2026-08-26-functional-coverage-covergroup-gap.md`): A minimal
   module-scope `covergroup`/`coverpoint` repro (kept in `/tmp/repro/`,
   not committed) confirmed the parser does not recognize the
   `covergroup` keyword at all -- a parse-level rejection, so no
   separate class-member repro was needed to establish the same result
   would hold there too. This is a bigger, cleaner-cut gap than most
   2026-08-23/24/25 findings (which had partial-support nuances) and
   matches the same category as 2026-08-26 first session's
   `randomize()`/`constraint` result: an entire IEEE 1800 verification
   feature area absent from this build. Notes also cover standard
   covergroup/coverpoint/cross/bins/`option.at_least` semantics and the
   coverage-as-stopping-criterion methodology point, independent of the
   tooling finding.

2. **A second tooling gap found while building the example**: an
   explicit `int'(op_raw)` cast of a `logic [2:0]` value crashes the
   elaborator (`assert: elab_expr.cc:2630`, "cast type and subject
   differ in signedness"); worked around with a plain assignment
   instead. Documented in both the notes and the example file's header.

3. **Code + results**
   (`examples/phase2/alu_manual_functional_coverage.sv`,
   `alu_manual_functional_coverage_sim_output_2026-08-26.txt`,
   `alu_manual_functional_coverage_wave.vcd`): Hand-implemented
   functional-coverage model reusing `alu_dut`, the scoreboard, and the
   dist-like/randc-like generators from `alu_manual_constrained_random.sv`
   (2026-08-26 first session) unmodified: a 5-bin opcode coverpoint, a
   3-bin operand-corner (ZERO/MAX/MID) coverpoint, a 15-cell cross
   between them, `at_least`-N-style closure targets, and a
   coverage-driven simulation loop that stops generating new stimulus
   once overall coverage reaches 100% (capped at 4000 transactions so a
   badly-tuned generator can't hang the run). Before committing to a
   corner-value draw rate, actually measured (not assumed) both a 1-in-4
   (matching the existing randomization example) and a 1-in-2 rate
   against the 4000-transaction cap -- both closed comfortably (252 and
   384 transactions respectively; 1-in-4 closed *faster* in this run,
   the opposite of the naive expectation, a reminder that with this
   build's deterministically-seeded `$urandom` this is one fixed draw
   sequence per rate, not a general statistical claim) -- and kept the
   established 1-in-4 rate rather than introducing an unmotivated
   difference from the existing file. Compiled and run with Icarus
   Verilog 10.3: 252 transactions, 0 scoreboard errors, all coverage
   bins (op, a_corner, and the 15-bin cross) closed at 100%. Real,
   non-empty VCD waveform captured and committed alongside the console
   output.

4. **Progress tracking**: marked "Functional coverage
   (covergroup/coverpoint/cross)" done in `progress.md`, with the same
   explicit-caveat style used for the 2026-08-26 first-session
   randomization entry (native tooling gap + workaround stated, not a
   bare checkmark).

**Next run should:** continue Phase 2 with "Basic SVA (`assert
property`, immediate vs. concurrent)." The 2026-08-23 notes already
found that *immediate* `assert` statements are unsupported on this
build; concurrent `assert property` (a materially different, more
complex SVA construct built on sequence/property expressions) has not
been tested at all and, given the pattern established across every
session since 2026-08-25 (constrained-random and now functional
coverage both entirely absent), should not be assumed to work --
confirm with a minimal repro before designing that session's example,
exactly as this session and the previous one did.

**Commits this run:** 4 (functional-coverage study notes, coverage
model code + compiled/simulated evidence, progress.md update, this log
entry).

---

## 2026-08-28

**Status:** Eighth automation run. No run is recorded for 2026-08-27 in
this log or in `git log` -- the previous entry (2026-08-26, second
session) is the most recent prior activity, so this run picked up
directly from its "next run should" recommendation rather than assuming
an intervening day's work exists.

**Environment note:** this session's container had no `iverilog`
preinstalled, but -- unlike the 2026-08-22/23 sessions that motivated
writing `tools/setup_iverilog.sh` as a no-root workaround -- this
session's container had working root/`apt-get` access, and the
distribution default pulled in Icarus Verilog 12.0 (not the 10.3 every
prior session's findings are based on). To keep today's findings
directly comparable to the existing tooling-gap corpus, this session
used `tools/setup_iverilog.sh` (confirmed via `iverilog -V` -> 10.3) as
the authoritative toolchain rather than the apt-installed version; the
12.0 result is recorded as a secondary, clearly-labeled data point in
today's notes rather than the basis for the committed example. Flagged
as a real (if minor) environment-stability finding: this repo's sandbox
is not identical session-to-session.

**Repo state at start:** Phase 1 complete; Phase 2's first four items
(SV data types/interfaces, OOP testbench components, randomization,
functional coverage) complete as of 2026-08-24 through 2026-08-26.
`progress.md`'s next unchecked item: "Basic SVA (`assert property`,
immediate vs. concurrent)." The 2026-08-26 (second session) notes
explicitly recommended confirming with a minimal repro before designing
an example, given the established pattern of native SV features turning
out to be entirely absent rather than partially supported -- exactly
what this session did.

**Work done:**

1. **Tooling investigation + study notes**
   (`notes/2026-08-28-sva-immediate-vs-concurrent-assertions.md`):
   Minimal repros against the genuine pinned Icarus Verilog 10.3
   confirmed immediate assertions are still not implemented ("sorry:
   Simple immediate assertion statements not implemented" -- re-verifying
   rather than assuming the 2026-08-23 finding still holds, per this
   repo's established practice), and additionally confirmed concurrent
   assertions (`assert property`, and a standalone `property...
   endproperty` block on its own) are also not supported ("sorry:
   concurrent_assertion_item not supported"). Net result: neither SVA
   syntax flavor is available on this build at all -- a total gap in the
   same category as 2026-08-26's randomize()/covergroup findings, not a
   partial-support nuance. As a secondary, explicitly-labeled data point,
   the same repros were also run against the apt-installed Icarus Verilog
   12.0: immediate assertions work there, concurrent assertions still do
   not. Notes also cover standard SVA concepts (sequences, properties,
   `|->`/`|=>` implication, `disable iff`, `assert`/`assume`/`cover`, and
   why assertion-based checking is architecturally distinct from
   scoreboard-based checking) independent of the tooling finding.
   WebSearch/WebFetch were available but not used for the concept
   material (stable IEEE 1800 LRM content), consistent with prior
   sessions' judgment on this point.

2. **Code + results**
   (`examples/phase2/alu_sva_checker.sv`,
   `alu_sva_checker_sim_output_2026-08-28.txt`,
   `alu_sva_checker_wave.vcd`): Since neither native assertion flavor is
   available, built a dedicated assertion-STYLE checker for the existing
   `alu_dut` (reused unmodified): an independent reference model (carry/
   borrow via comparison rather than a widened add/subtract; overflow via
   a sign-extended-truncation check rather than a sign-bit XOR --
   deliberately different arithmetic formulations from the DUT's own, so
   a shared bug in "the obvious way to compute this" cannot silently
   cancel out between DUT and checker) checked against DUT outputs every
   cycle via the established `if (!cond) $error(...)` idiom, structured
   as a separate checker task decoupled from stimulus application (the
   architectural point a real concurrent-assertion-based checker would
   also embody, independent of concrete syntax). Includes one deliberate,
   clearly-labeled corrupted-expectation case (mirroring
   `sync_fifo_directed_tb.v`'s illegal-push/illegal-pop pattern) proving
   the checker actually fires rather than only ever passing. Two further
   tooling gaps found and worked around while building this file
   (documented in both the notes and the example's own header): a
   `function` with `output` arguments is rejected on this build (worked
   around with a `task` instead); `enum_value.name()` in a `$error`
   format argument is rejected (worked around by printing the raw
   enum value with `%0d`). Compiled and run with the pinned Icarus
   Verilog 10.3: 15 checks total, 14/14 real checks matched the
   independent reference model, and the one deliberate corrupted-
   expectation case correctly failed with the expected message. Real,
   non-empty VCD waveform captured and committed alongside the console
   output.

3. **Progress tracking**: marked "Basic SVA (assert property, immediate
   vs. concurrent)" done in `progress.md`, with the same explicit-caveat
   style used for the 2026-08-26 randomization/coverage entries (total
   tooling gap + workaround stated, not a bare checkmark).

**Next run should:** continue with Phase 2's final remaining item, the
phase milestone itself: "constrained-random SV testbench w/ scoreboard +
coverage for a small DUT" -- integrating the manual-workaround
randomization (2026-08-26), functional-coverage (2026-08-26 second
session), and assertion-style checker (this session) into one combined
testbench for a single DUT, rather than the three separate demonstration
files that exist today. Before starting, run `iverilog -V` and compare
against this session's pinned-10.3 approach (Section 0 of today's notes)
-- do not assume the same toolchain setup path is needed without
checking first, given today's environment finding.

**Commits this run:** 3 (SVA study notes + tooling findings, assertion-
style checker code + compiled/simulated evidence, progress.md update;
this AUTOMATION_LOG.md update commit makes 4).

---

## 2026-08-29 — Phase 2 milestone: combined testbench; Phase 2 complete

**Status:** Ninth automation run.

**Repo state at start:** Phase 1 complete; Phase 2's first four items (SV
data types/interfaces, OOP testbench components, randomization,
functional coverage, and basic SVA) all complete as of 2026-08-24 through
2026-08-28. `progress.md`'s only remaining Phase 2 item: the phase
milestone itself, "constrained-random SV testbench w/ scoreboard +
coverage for a small DUT." The 2026-08-28 entry explicitly recommended
integrating the three existing manual-workaround examples
(randomization, functional coverage, assertion-style checker) into one
combined testbench for this milestone, rather than leaving them as three
separate demonstration files -- exactly what this session did.

**Environment note:** as in 2026-08-28, this session's container had
working root/`apt-get` access and the distribution default pulled in
Icarus Verilog 12.0. Checked `iverilog -V` before starting, per the
2026-08-28 entry's explicit recommendation, and again used
`tools/setup_iverilog.sh` (pinned Icarus Verilog 10.3) as the
authoritative toolchain for direct comparability with the existing
gap corpus. As a secondary data point, also compiled and ran today's new
file against the apt-installed 12.0: it compiled cleanly but `vvp`
segfaulted immediately at simulation start, producing no output at all --
a genuine 12.0-vs-10.3 compatibility difference, not investigated
further, and not the basis for today's committed result.

**Work done:**

1. **Code + results**
   (`examples/phase2_milestone/alu_combined_tb.sv`,
   `alu_combined_sim_output_2026-08-29.txt`, `alu_combined_wave.vcd`):
   Combined, in one testbench module driving one `alu_dut` instance: the
   transaction class + dist-like weighted opcode generator + randc-like
   corner-value generator from `alu_manual_constrained_random.sv`
   (2026-08-26); the coverpoint/cross bin-counting functional-coverage
   model + coverage-driven stopping criterion from
   `alu_manual_functional_coverage.sv` (2026-08-26, second session); and,
   run independently alongside the existing scoreboard on every
   transaction (deliberately NOT merged into one shared reference model --
   see the file header and today's notes for why keeping two
   independently-formulated checks matters architecturally), the
   assertion-style checker from `alu_sva_checker.sv` (2026-08-28). All
   three sources' logic was reused essentially unmodified; no new Icarus
   10.3 tooling gaps were found while integrating them, and the combined
   file compiled and ran cleanly on the first attempt. **Actually
   compiled and run** with the pinned Icarus Verilog 10.3: 252 scoreboard
   checks / 0 errors; 253 assertion-checker checks (252 real + 1
   deliberate corrupted-expectation case, which correctly failed) / 252
   passed; all three functional-coverage components (5-bin op
   coverpoint, 3-bin a_corner coverpoint, 15-bin cross) closed at 100%
   after 252 transactions. Real, non-empty VCD waveform (11155 lines)
   captured alongside the console output. Testbench's own final verdict:
   PASS.

2. **Study notes**
   (`notes/2026-08-29-phase2-milestone-combined-testbench.md`): Documents
   the integration approach and rationale (why two independently-
   formulated checkers rather than one shared model), the re-confirmed
   tooling status (no new gaps), the 12.0 segfault finding, and the full
   results.

3. **Progress tracking**: marked the Phase 2 milestone done in
   `progress.md`, with the same explicit-caveat style used throughout
   this phase (native constrained-random/coverage/SVA are all
   hand-implemented workarounds on this build, stated plainly).

**Phase 2 (SystemVerilog for Verification) is now fully complete.**

**Web search availability:** WebSearch/WebFetch were available this
session but not used -- today's work was pure integration of
already-researched, already-verified-working prior content, with no new
conceptual or literature material requiring search.

**Next run should:** begin Phase 3 (Verification Methodology
Fundamentals): layered testbench architecture concepts, TLM basics, and
verification planning, per the roadmap README. Phase 3's milestone is a
written verification plan (markdown, in this repo) for a moderately
complex DUT (README suggests a simple APB/AHB-lite peripheral or a UART)
that becomes the spec for the Phase 4 UVM testbench -- unlike Phase 2,
this milestone is a planning document rather than simulator-dependent
code, so tooling-gap risk is lower for the deliverable itself, though any
illustrative snippets should still be spot-checked against this build's
established gap list (SV data types/interfaces mostly usable;
classes/OOP usable with the documented workarounds; randomize()/
covergroup/SVA all absent) before being presented as running examples.

**Commits this run:** 2 (combined milestone testbench code + notes +
compiled/simulated evidence, progress.md update; this AUTOMATION_LOG.md
update commit makes 3).

## 2026-08-31 — Phase 3 begins: layered testbench architecture + TLM basics

**Status:** Tenth automation run (first run after a two-day gap; no
2026-08-30 session occurred).

**Repo state at start:** Phase 1 and Phase 2 both fully complete as of
2026-08-29. `progress.md`'s first unchecked item: Phase 3's "Layered
testbench architecture concepts," per the README's phase ordering.

**Work done:**

1. **Study notes**
   (`notes/2026-08-31-layered-testbench-architecture-and-tlm-basics.md`):
   Covers two `progress.md` items together -- "Layered testbench
   architecture concepts" and "TLM basics" -- since TLM is the
   mechanism the architecture's layers communicate through and the two
   don't separate cleanly. WebSearch/WebFetch were available and used
   (Maven Silicon and Verification Guide testbench-architecture
   write-ups; ChipVerify's TLM analysis-port page) alongside stable
   IEEE 1800/UVM methodology background. Covers: why a layered
   architecture over a directed testbench (reuse; separating stimulus
   from checking so randomized/coverage-driven stimulus becomes
   possible later); the standard layer roles (transaction, sequencer/
   generator, driver, monitor, agent, scoreboard, environment, test);
   TLM's port/export/imp roles and analysis-port broadcast (`write()`)
   semantics and why decoupled channels (not direct object references)
   are what makes the layers reusable.

   Section 4 goes further than a generic conceptual writeup: it
   synthesizes this repo's own already-logged Phase 2 tooling gaps
   (`mailbox` unimplemented, a class cannot hold a `virtual <interface>`
   member, class handles cannot be passed as `input`/`ref` arguments or
   stored in queues/arrays -- all from
   `notes/2026-08-25-oop-testbench-components.md`) into one unified
   explanation: this repo's pinned Icarus Verilog 10.3 build cannot
   express a driver or monitor as a real class object at all (only
   transaction/generator/scoreboard), which is *why* Phase 2's OOP and
   milestone examples always left DUT pin-driving/sampling as
   procedural code adjacent to the transaction hand-off rather than
   inside separate driver/monitor classes -- previously stated as
   individual tooling notes without this connecting explanation.
   Confirms (does not overturn) the 2026-08-25 conclusion that Phase 4's
   real UVM milestone will need a different simulator. No new example
   code file was added this session: a fresh illustrative snippet would
   either duplicate `alu_oop_tb_components.sv`/`alu_combined_tb.sv` or
   re-hit the same already-documented gaps without adding anything, so
   this session's contribution is the synthesis/explanation rather than
   another compiled artifact.

2. **Progress tracking**: marked both "Layered testbench architecture
   concepts" and "TLM basics" done in `progress.md`, with the same
   explicit-caveat style used throughout Phase 2 (what's conceptually
   covered vs. what this specific toolchain can/cannot demonstrate,
   stated plainly rather than glossed over).

**Environment note:** `apt-get install iverilog` succeeded this session
(pulled the distribution default, 12.0, same as 2026-08-28/2026-08-29);
`tools/setup_iverilog.sh` (pinned 10.3) was also sourced successfully
for continuity with the existing gap corpus, though no code was
compiled either way this session since today's work was notes-only.

**Not yet covered (candidates for future runs):**
- Remaining Phase 3 items: verification planning (features -> checks ->
  coverage -> tests) and directed-vs-constrained-random-vs-coverage-
  driven trade-offs, both of which presuppose today's vocabulary
- Phase 3 milestone: a written verification plan (markdown) for a
  moderately complex DUT (README suggests a simple APB/AHB-lite
  peripheral or a UART), to become the Phase 4 UVM testbench's spec
- Before Phase 4 (UVM) begins in earnest, resolve the toolchain
  question flagged again this session and originally raised
  2026-08-25: this Icarus 10.3 build cannot host a real UVM
  environment (no virtual-interface class members, no mailbox, no
  class-handle containers) -- a different simulator or toolchain
  strategy needs to be chosen before Phase 4's coding milestones,
  not discovered mid-Phase-4

**Web search availability:** WebSearch/WebFetch were both available and
used this session.

**Commits this run:** 2 (layered-testbench-architecture + TLM-basics
study notes, progress.md update; this AUTOMATION_LOG.md entry commit
makes 3).

## 2026-09-05 — Phase 3 completes: verification planning + UART verification plan

**Status:** Eleventh automation run (first run after a five-day gap; no
sessions occurred 2026-09-01 through 2026-09-04).

**Repo state at start:** Phase 1 and Phase 2 fully complete. Phase 3's
first two items (layered testbench architecture, TLM basics) were
completed 2026-08-31; the remaining three `progress.md` items --
verification planning, directed/CRV/CDV trade-offs, and the Phase 3
milestone (a written verification plan for a chosen DUT) -- were still
unchecked.

**Work done:**

1. **Study notes**
   (`notes/2026-09-05-verification-planning-and-stimulus-strategy-
   tradeoffs.md`): Covers the two remaining conceptual `progress.md`
   items together, since the planning process is what decides which
   stimulus strategy applies per feature. WebSearch/WebFetch were
   available and used (all three fetches succeeded this session, unusual
   compared to several prior sessions' partial access failures): OpenHW
   Group's CORE-V-VERIF project's own verification-planning guide (a
   real, in-production open-source RISC-V project, used for the
   features->checks->coverage->tests column structure and its RV32I
   ADDI "minimal sufficient coverage" worked example), ChipVerify's
   seven-section vplan template (incl. its own UART-parity coverage
   worked example, reused directly in today's plan since it's this
   session's actual chosen DUT), and "The Art of Verification"'s
   directed-vs-constrained-random trade-off discussion (strengths/
   weaknesses of each, and the recommended CRV-then-directed-gap-filling
   hybrid). Connected the trade-off discussion back to this repo's own
   Phase 2 milestone (`alu_combined_tb.sv`, 2026-08-29) as an
   already-built, hand-implemented instance of the coverage-driven loop
   being described.

2. **Verification plan (Phase 3 milestone)**
   (`verification_plans/uart_controller_verification_plan.md`, new file/
   new top-level folder): A full spec-first verification plan for a UART
   controller with a register interface (6-register APB-lite-style map),
   TX/RX FIFOs (8 deep), and an interrupt output -- deliberately the same
   DUT already named in this repo's own README as the Phase 6 capstone
   project, so this doubles as an early capstone vplan draft rather than
   a one-off exercise DUT needing later re-planning. Nine features
   (F1-F9: register access, TX/RX data paths, parity, TX/RX FIFO
   management incl. overrun, baud-rate generation, interrupt generation,
   loopback mode), each with stated checks, functional-coverage
   coverpoints/crosses, and an explicit directed/constrained-random/
   coverage-driven strategy assignment reasoned from today's trade-off
   notes (7 directed tests total, everything else CRV/CDV) -- plus a
   14-test test list, a coverage plan (100% functional coverage target,
   95% code coverage target once RTL exists), sign-off criteria, and an
   explicit "out of scope for v1" section (configurable data-bit width,
   APB wait states, CDC, flow control, break detection) rather than
   silently omitting them. No RTL or testbench code exists for this DUT
   yet -- entirely a planning artifact, as the README's Phase 3 milestone
   description calls for.

3. **Progress tracking**: marked all three remaining Phase 3 items done
   in `progress.md` (verification planning, trade-offs, and the milestone
   itself), added the "Phase 3 is now fully complete" marker (matching
   the style used for Phase 2), and updated the Phase 6 capstone's
   "Verification plan written" sub-item to `[~]` (in progress) noting
   today's document as an early draft to be revised once Phase 4
   RTL/bring-up experience exists, rather than marking it fully done at
   the capstone level.

**Environment note:** `apt-get install iverilog` succeeded this session
(pulled the distribution default, 12.0); `tools/setup_iverilog.sh` (pinned
10.3) was also sourced successfully. Neither was actually needed this
session since today's work was planning/notes-only (no RTL or testbench
code was written) -- sourced anyway for continuity, consistent with the
2026-08-31 session's practice.

**Phase 3 (Verification Methodology Fundamentals) is now fully complete.**

**Not yet covered (candidates for future runs):**
- Phase 4 (UVM) begins next per the roadmap. Before its coding milestones,
  the toolchain question flagged repeatedly since 2026-08-25 (this repo's
  pinned Icarus 10.3 build cannot host a real UVM environment: no
  virtual-interface class members, no `mailbox`, no class-handle
  containers) still needs a concrete resolution -- not discovered
  mid-Phase-4.
- No UART RTL exists yet anywhere in this repo -- today's verification
  plan is spec-first; Phase 4 will need the DUT written (or sourced)
  before any of today's planned tests can actually be coded and run.
- Today's plan flags its own open item: the F7 baud-rate tolerance number
  cannot be finalized without real RTL to measure rounding/timing
  behavior against.

**Web search availability:** WebSearch/WebFetch were both available and
used this session; all three fetches succeeded (no access failures to
record this session, unlike several prior sessions in this log).

**Commits this run:** 3 (verification-planning + trade-offs study notes,
UART verification plan, progress.md update; this AUTOMATION_LOG.md entry
commit makes 4).

## 2026-09-06 — Phase 4 toolchain resolved: real UVM environment via uvm-python

**Status:** Twelfth automation run.

**Repo state at start:** Phases 1-3 fully complete. Phase 4 (UVM) not yet
started. Every Phase 2/3 session since 2026-08-25 had flagged the same
standing blocker: this repo's pinned Icarus Verilog build cannot compile
SystemVerilog classes at all (no `mailbox`, no `virtual <interface>`
class members, no class handles as `input`/`ref` args or in
queues/arrays), so a native SV-UVM environment is impossible here. The
2026-09-05 session's "not yet covered" list repeated this again as the
thing to resolve before Phase 4's coding milestones begin. This session
prioritized that resolution directly, with a real running artifact, over
starting Phase 4's conceptual notes on top of an unresolved toolchain
question.

**Work done:**

1. **Research notes**
   (`notes/2026-09-06-uvm-python-toolchain-resolution.md`): WebSearch and
   WebFetch were both available and used (all fetches succeeded). Weighed
   three options: a different HDL simulator (rejected -- Verilator has no
   class support either, and a commercial simulator isn't licensed here);
   bare cocotb (real class-based driver/monitor, but no UVM factory/
   phasing/hierarchy, so it wouldn't actually satisfy the Phase 4
   checklist items); and uvm-python
   (https://github.com/tpoikela/uvm-python), a Python/cocotb port of UVM
   1.2 whose own docs state Icarus Verilog is "fully supported and
   recommended." Chose uvm-python. Also documents two real,
   reproducible installation gotchas hit and fixed this session:
   `python-constraint` (a `cocotb-coverage` dependency) fails to build
   against modern `setuptools` unless installed with `--use-pep517`
   first, and uvm-python 0.4.0 is incompatible with the latest cocotb
   (2.1.0 -- `cocotb.utils.simulator` was removed in cocotb 2.x) and
   needs `cocotb<2.0` pinned explicitly.

2. **Code + results** (`examples/phase4_uvm_python/`): A real UVM
   environment (`AluSeqItem`/`AluRandomSequence` as genuine
   `UVMSequenceItem`/`UVMSequence` classes, `AluDriver`/`UVMSequencer` via
   the actual pull-mode `seq_item_port` handshake, `AluMonitor`
   broadcasting over a real `UVMAnalysisPort`, `AluScoreboard` receiving
   via `uvm_analysis_imp_decl`, `AluAgent`/`AluEnv`/`AluTest` component
   hierarchy, all factory-registered via `uvm_component_utils`/
   `uvm_object_utils`, driven by the standard phase machine with
   objection-based termination) running against the unmodified Phase 2
   `alu_dut` (`examples/phase2/alu_if_and_dut.sv`) on this repo's pinned
   Icarus build. Two genuine bugs were found and fixed while bringing
   this up (both documented in the code's comments, not silently
   patched): uvm-python enforces that `run_test()` must be called at
   simulation time 0 with no preceding delay, which required moving DUT
   reset from the cocotb test function into `AluTest.run_phase`; and a
   driver/monitor edge-alignment race silently dropped the first
   transaction (`driven=40` but `sampled=39`, found via added
   driven/valid_seen/result_valid_seen/sampled instrumentation and
   per-transaction sim-time prints), root-caused to the first
   transaction's `valid` assertion coinciding with the same simulation
   timestep as the monitor's `RisingEdge` sampling coroutine, fixed by
   having the driver explicitly synchronize to `FallingEdge` every
   iteration rather than relying on incidental timing. Final result:
   `driven=40 sampled=40 checked=40 errors=0`, `TESTS=1 PASS=1`
   (`alu_uvm_tb_sim_output_2026-09-06.txt`).

3. **Progress tracking**: marked "UVM class hierarchy, phases, factory
   pattern" done in `progress.md`, marked "TLM ports/exports/analysis
   ports, sequences/sequencers" and "Drivers, monitors, active/passive
   agents" as in-progress (`[~]`) with explicit notes on what is and
   isn't yet demonstrated (virtual sequencers, multiple concurrent
   sequences, and the active/passive agent distinction are not yet
   covered), and added a toolchain-resolution note at the top of the
   Phase 4 section pointing to today's research notes.

**Not yet covered (candidates for future runs):**
- Virtual sequencers and multiple concurrent sequences (Phase 4 checklist
  item only partially covered by today's single-sequence example)
- Factory *overrides* specifically (today's config_db usage is plain
  `set`/`get`, not an override)
- RAL (register abstraction layer) basics -- uvm-python claims partial
  support per its own docs but nothing has exercised it yet
- The `cocotb-coverage`-wants-`cocotb>=2.0` vs. `uvm-python`-needs-
  `cocotb<2.0` version conflict noted in today's research notes is
  unresolved; matters if a future session needs `cocotb-coverage`'s
  functional-coverage primitives under uvm-python
- The actual Phase 4 milestone (a full UVM testbench w/ 2-3 sequences/
  tests + coverage target, per the README) needs a larger DUT than the
  8-bit ALU and has not been attempted yet -- today's work is a
  toolchain proof-of-concept, not the milestone itself
- Graphene-repo-side "not yet covered" items are tracked separately in
  that repo's own AUTOMATION_LOG.md, not here

**Web search availability:** WebSearch/WebFetch were both available and
used this session; all fetches succeeded.

**Commits this run:** 3 (uvm-python toolchain research notes, the
alu_uvm_tb.py UVM environment + Makefile + sim output, progress.md
update; this AUTOMATION_LOG.md entry commit makes 4).

## 2026-09-07 — Phase 4: factory overrides (closes the Configuration checklist item)

**Status:** Thirteenth automation run.

**Repo state at start:** Phases 1-3 fully complete. Phase 4 toolchain
resolved 2026-09-06 (uvm-python on the pinned Icarus build); the "UVM
class hierarchy, phases, factory pattern" checklist item done, "TLM
ports/exports/analysis ports, sequences/sequencers" and "Drivers,
monitors, active/passive agents" in progress (`[~]`), and "Configuration
(`uvm_config_db`, factory overrides)" only half-done: plain
`UVMConfigDb.set`/`get` demonstrated, factory overrides explicitly
flagged as not yet demonstrated. This session closed that remaining
half.

**Work done:**

1. **Toolchain reinstall.** This run started in a fresh container with
   none of 2026-09-06's toolchain present (no iverilog, no cocotb, no
   uvm-python). Reinstalled via the exact documented sequence
   (`notes/2026-09-06-uvm-python-toolchain-resolution.md`): `apt-get
   install iverilog` (12.0), `pip install --use-pep517
   python-constraint`, `pip install uvm-python` (pulls in `cocotb>=2.0`),
   then `pip install "cocotb<2.0"` again to re-pin it (uvm-python 0.4.0
   is still incompatible with cocotb 2.x, confirmed unchanged). Re-ran
   the existing `alu_uvm_tb.py` test first, unmodified, to confirm the
   reinstalled toolchain reproduces 2026-09-06's exact result
   (`driven=40 sampled=40 checked=40 errors=0`) before writing anything
   new.

2. **Bug fix + gap analysis**
   (`examples/phase4_uvm_python/alu_uvm_tb.py`,
   `notes/2026-09-07-factory-overrides-and-config-db.md` Section 2):
   found that `AluAgent.build_phase`/`AluEnv.build_phase` created every
   child via direct Python constructor calls rather than
   `<Class>.type_id.create(name, parent)` -- harmless for 2026-09-06's
   purposes (no override was in use) but a silent trap for today's work,
   since a factory override only takes effect if creation is actually
   routed through the factory; registering one against a component whose
   parent constructs it directly would succeed with no error and then
   simply never be consulted. Fixed by routing all child creation
   (`sequencer`, `driver`, `monitor`, `agent`, `scoreboard`) through
   `type_id.create()`. Verified behavior-preserving: re-ran the baseline
   test, got the identical `driven=40 ... errors=0` result.

3. **Code + results**
   (`examples/phase4_uvm_python/alu_uvm_factory_override_common.py`,
   `alu_uvm_factory_type_override_tb.py`,
   `alu_uvm_factory_inst_override_tb.py`, two new Makefiles, two sim
   output logs): implemented both UVM factory override entry points --
   `set_type_override` (global) and `set_inst_override` (path-specific,
   `"uvm_test_top.env.scoreboard"`) -- each substituting a shared
   drop-in `AluScoreboardOpHistogram(AluScoreboard)` (identical checking
   behavior via `super().write_alu()`, plus a per-opcode pass/fail
   histogram reported through a `report_phase` override, a UVM phase not
   otherwise used anywhere in this repo) for the environment's plain
   `AluScoreboard`, with zero changes to `AluEnv`/`AluAgent` source.
   Found and fixed a verification-timing bug while writing these: the
   first version asserted the override's effect immediately after
   `super().build_phase()` inside the test's own `build_phase`, which
   failed with `self.env.scoreboard is a NoneType` -- not because the
   override didn't work, but because UVM's topdown build traversal
   hasn't yet invoked the newly-constructed `env`'s own `build_phase()`
   at that point. Fixed by moving the verification to `connect_phase`,
   which UVM guarantees only runs after the whole tree's build phase has
   completed. Both tests now pass with a real, checked assertion (not
   just log output) confirming the override took effect, plus the
   printed per-opcode histogram (`ADD/SUB/AND/OR/XOR pass/fail`, 40/40
   total transactions, 0 failures, matching the baseline scoreboard's own
   result). Full design writeup, including why the two tests'
   *observable* results are identical in this single-scoreboard
   environment (stated explicitly rather than implied otherwise), in
   `notes/2026-09-07-factory-overrides-and-config-db.md`.

4. **Progress tracking** (`progress.md`): marked "Configuration
   (`uvm_config_db`, factory overrides)" `[x]`, with a summary of what
   was demonstrated and a pointer to today's notes file for the
   `type_id.create()` prerequisite fix.

**Not yet covered (candidates for future runs):**
- Virtual sequencers and multiple concurrent sequences (still open from
  2026-09-06 -- today's work did not touch this)
- Active/passive agent distinction (still open -- today's agent remains
  active-only)
- RAL (register abstraction layer) basics -- still unexercised
- The actual Phase 4 milestone (a full UVM testbench w/ 2-3 sequences/
  tests + coverage target) needs a larger DUT than the 8-bit ALU and has
  not been attempted
- A behavioral contrast between type and instance overrides (as opposed
  to just demonstrating both API calls correctly) would need a second
  `AluScoreboard` instance elsewhere in a larger environment -- not
  present in this repo's single-scoreboard ALU testbench

**Web search availability:** Not needed this session (toolchain-internal
UVM/factory-API investigation and hands-on debugging, not a literature
review).

**Commits this run:** 3 (factory-overrides research/design notes, the
alu_uvm_tb.py factory-create fix + new factory-override testbench files
+ sim output logs, progress.md update; this AUTOMATION_LOG.md entry
commit makes 4).

---

## 2026-09-17 — Phase 4: the UART DUT gets written, and a testbench that passed against broken RTL

**Status:** Phase 4 in progress. The Phase 4 milestone had been gated
since 2026-09-05 on a DUT that did not exist; it exists now and is
verified. Note on repo history: the last commit before this session was
2026-09-07, so the 2026-09-08..09-16 window has no sessions recorded
here (see "Automation health" below — this was a broken-automation gap,
not a decision to pause).

**Work done:**

1. **DUT RTL** (`rtl/uart_controller.v`, 394 lines, Verilog-2001): the
   UART controller specified by
   `verification_plans/uart_controller_verification_plan.md` Section 1 —
   APB-lite register interface (`pready` tied high per the Section 1.2
   scope reduction), all six registers of the Section 1 map, 8-entry x
   8-bit TX/RX FIFOs in a single clock domain, a 16x-oversample baud
   generator giving bit rate `clk/(16*(div+1))`, TX/RX framing FSMs
   (start, 8 data LSB-first, optional even/odd parity, 1 or 2 stop bits,
   mid-bit RX sampling with start-bit glitch rejection),
   `CTRL.loopback_en`, and a masked level `irq`. Written in
   Verilog-2001 specifically so it runs on the pinned Icarus 10.3
   build: the class-support wall logged since 2026-08-25 applies to
   class-based *testbenches*, not to synthesizable RTL. The Phase 1-3
   8-bit ALU was never going to carry this plan's nine features (no
   registers, no FIFOs, no serial framing, no interrupt), which is why
   the milestone was stuck.

   **Contradicts the verification plan, deliberately and explicitly:**
   the plan (Section 1) calls all seven STATUS bits "live status". The
   four occupancy bits are combinational as specified, but the three
   error bits (`frame_err`, `parity_err`, `overrun_err`) are
   implemented **sticky, cleared on a STATUS read** (16550 LSR style).
   A truly combinational error bit is asserted for one clock cycle and
   therefore cannot be observed by any register read at all, which
   would make the plan's own F4 and F6 checks untestable. Stated in the
   RTL header comment, the notes file, `progress.md` and here rather
   than quietly changing the plan text; the vplan needs a v2 revision
   to match (its Section 7 explicitly anticipated RTL-informed
   corrections of this kind).

2. **Bring-up regression** (`examples/phase4_rtl_bringup/
   uart_controller_tb.v` + committed sim output log): 60 directed
   self-checking tests, T1-T12, mapped to plan features F1-F9 — reset
   values; register R/W with bit masking, ignored writes to read-only
   STATUS, a defined read of write-only TX_DATA, and a no-hang
   undefined-address read; loopback framing across no/even/odd parity
   and 1 and 2 stop bits; TX FIFO fill, `tx_full`, write-while-full as
   a safe no-op, and in-order drain of all eight bytes; RX overrun
   (9th byte dropped, `overrun_err` set, existing eight entries
   intact); measured TX bit period against `16*(div+1)*clk`; interrupt
   masking; and two negative tests driven from a standalone bit-level
   RX driver (corrupted parity, bad stop bit). Result: **60 passed, 0
   failed.** Every check prints expected vs. actual and increments a
   failure counter, with `$fatal` on failure and a global watchdog, so
   neither a broken nor a hung DUT can pass quietly.

   Deliberately **not** a UVM testbench: bringing up a new DUT inside a
   brand-new UVM environment makes every failure ambiguous between a
   DUT bug and a UVM bug. The UVM environment now gets built against a
   DUT already known good. The plan's Section 2.4 prediction that
   corrupted-parity testing would require a standalone RX bit-driver
   (unreachable via loopback, since a working TX never sends bad
   parity) held exactly.

3. **The actual finding of the session** (`notes/2026-09-17-uart-rtl-
   bringup-and-status-polling-hazard.md`, plus
   `examples/phase4_rtl_bringup/mutation_test_report_2026-09-17.txt`):
   the first complete version of this regression reported 55 passed, 0
   failed — and went on reporting 55 passed, 0 failed against RTL
   deliberately mutated to compute even parity where odd was required.
   Mutation testing (inject one defect into a copy of the RTL, require
   the regression to fail) is what exposed it.

   Root cause: `parity_err` is read-to-clear, and the testbench's wait
   helper polled STATUS in a loop until `rx_avail` came up — so by the
   time the test read STATUS to check `parity_err`, its own polling
   loop had already cleared it. The check was not weak and the injected
   bug was not subtle; the *measurement apparatus* had a side effect on
   the thing being measured. This generalises to any register interface
   with read-to-clear or read-destructive fields (RX FIFO pops, W1C
   interrupt flags, clear-on-read counters), and it reappears in UVM as
   a monitor or `wait_for_status()` utility issuing real bus reads.
   Fixed by replacing the poll with a counted `wait_bits()` and
   checking every field from a single STATUS snapshot. After the fix:
   60 checks, and all five injected mutations detected (m1 TX odd
   parity 59/60 FAILED, m2 overrun overwrites 56/60 FAILED, m3 `irq`
   ignores mask 57/60 FAILED, m4 RX samples at bit edge 36/60 FAILED,
   m5 baud reload off by one 25/60 FAILED).

   Worth noting honestly: m1 is caught by exactly *one* check, because
   loopback is this suite's only TX-parity observation point. That is
   thin, and it is a concrete argument for the plan's Section 2.2
   `tx`-line monitor with an independent reference bit-stream
   generator — which belongs in the UVM environment.

4. **Progress tracking** (`progress.md`): recorded the DUT under Phase
   4, marked the milestone as no longer blocked on a missing DUT (what
   remains is the UVM environment itself), and flagged the Phase 6
   capstone vplan as needing a v2 revision for the STATUS sticky-bit
   correction.

**Not yet covered (candidates for future runs):**
- The Phase 4 UVM environment against the now-verified `uart_controller`
  RTL: register-bus agent, serial-line agent (including the standalone
  RX bit-driver F4 needs), reference-model scoreboard, functional
  coverage collector — this is now the single clear next step, and is
  no longer blocked on anything
- A `tx`-line monitor with an independent reference bit-stream generator
  (plan Section 2.2's actual specified check) — the concrete fix for
  m1's thin single-check detection
- vplan v2 revision: the STATUS sticky/read-to-clear correction, and
  finalising the F7 baud tolerance now that real RTL exists to measure
  (plan Section 6, sign-off item 5, was explicitly left open pending RTL)
- RAL basics — still untouched; note the UART now gives it a real
  register map to model, which the ALU never did
- Virtual sequencers and multiple concurrent sequences (open since
  2026-09-06; untouched again today)
- Active/passive agent distinction (open; the existing ALU agent remains
  active-only). The UART's loopback vs. external-RX modes are a natural
  home for a passive monitor-only agent
- Constrained-random and coverage-driven stimulus for the UART (plan
  Sections 2-3 assign most features to CRV); today's suite is entirely
  directed, by design, since its job was DUT bring-up
- Code coverage measurement (plan Section 5 targets 95%) — not attempted;
  Icarus has no native coverage support, so this needs its own toolchain
  investigation

**Automation health (needs Harsh's attention, reported separately):**
This session ran interactively rather than unattended, and found why the
2026-09-08..09-16 gap exists: the scheduled task's device shell has no
GitHub push credentials (`git push` fails with `could not read Username
for 'https://github.com'`; no credential helper, no `gh`, and SSH cannot
resolve github.com through the HTTPS-only proxy), and the session VM is
rebuilt per run so nothing persists. Separately, `git` cannot operate
inside the connected folder at all, because it must unlink its own
`.git/*.lock` files and deletion in connected folders is denied. Today's
commits were therefore made in the session's own scratch clone and
delivered as git bundles for Harsh to push manually. Until credentials
are resolved, unattended runs cannot push.

**Web search availability:** Not needed this session — RTL design against
an already-researched in-repo specification plus hands-on debugging, not
a literature review. No fetches attempted, so no access failures to
record.

**Commits this run:** 4 (UART RTL; bring-up regression + sim output log +
mutation report; the read-to-clear/mutation-testing notes file;
progress.md update). This AUTOMATION_LOG.md entry commit makes 5.

---

## 2026-09-18 — Phase 4 milestone complete, and a green regression that was hiding UVM_ERRORs

**Status:** Full session. **The Phase 4 UVM milestone is complete.** Only
RAL basics remains in Phase 4.

**Work done:**

1. **The milestone environment**
   (`examples/phase4_uvm_milestone/uart_uvm_tb.py`, ~1030 lines, plus a
   Makefile, the sim log and a mutation report): a full UVM environment
   on uvm-python/cocotb/Icarus 10.3 against the **unmodified**
   `rtl/uart_controller.v` brought up on 2026-09-17. Closes three of the
   four things `progress.md` still listed as unexercised:
   - **Active vs passive agents.** One `UartSerialAgent` class,
     instantiated ACTIVE on the `rx` input (sequencer + driver + monitor)
     and PASSIVE on the `tx` output (monitor only, neither child built).
     Chosen because it is the case where the distinction is *forced*:
     `tx` is a DUT output, so an agent there physically cannot be active.
     `connect_phase` asserts at runtime that the passive instance built
     no driver and no sequencer — a flag that is merely set is not an
     exercise of the concept.
   - **Virtual sequencer and concurrent sequences.**
     `UartVirtualSequencer` holds both real sequencers;
     `UartFullDuplexVSeq` reaches it through `get_sequencer()` (uvm-python
     names the field `m_sequencer`; there is no `self.sequencer`
     property — one debug cycle) and starts register-side TX and
     serial-side RX stimulus *simultaneously* via `cocotb.start_soon`.
     The DUT therefore transmits and receives at the same time, which
     back-to-back sequences can never produce.
   - **Reference-model scoreboard** on three analysis imps
     (`_reg`/`_rx`/`_tx`): predicts tx frames from TX_DATA writes,
     predicts RX_DATA reads from frames observed on rx, and models the
     STATUS error bits as sticky/read-to-clear. Fed only from monitors,
     never from drivers.

   Baseline: **69 scoreboard checks, 0 errors, 12 rx + 15 tx frames
   decoded, 100.0% functional bin coverage** over 5 coverpoints and one
   cross, under three frame formats (none/1 stop, even/1, odd/2).
   Coverage below target raises a UVM_ERROR rather than printing a number
   nobody reads.

2. **Mutation testing — and the two real testbench defects it exposed.**
   Five defects injected into *copies* of the RTL. Final result **5/5
   killed, 0 survivors**, but the first pass reported two survivors and
   both were testbench bugs, not lucky RTL:

   **Defect A — the regression reported PASS while the scoreboard
   reported errors.** Mutants M1 (TX parity inverted) and M2 (RX shifted
   MSB-first) were correctly *detected*: the scoreboard printed
   `UVM_ERROR ... got 1, expected 0`. cocotb still recorded
   `TESTS=1 PASS=1 FAIL=0`. cocotb's verdict comes from whether the test
   coroutine raised; it has no knowledge of the UVM report server's
   severity counts, and uvm-python does not bridge the two. The log
   contained the evidence and the summary line contradicted it.

   This is the **same class as the 2026-09-17 finding** (a testbench that
   passed 55/55 against deliberately broken RTL) arrived at from the
   opposite direction — there the checks never ran, here they ran,
   failed, printed, and were ignored. Arguably worse, because it teaches
   a reader to trust a summary line that is wrong. Fixed:
   `UartMilestoneTest.report_phase` reads the report server's
   UVM_ERROR/UVM_FATAL counts and asserts zero (report_phase is
   bottom-up, so all children are already counted).

   **Defect B — checking that a sticky bit SETS is not checking a
   read-to-clear register.** With A fixed, M3 (read-to-clear deleted)
   still survived: one STATUS read per run cannot distinguish a bit that
   never clears from one correctly re-set by the next run's injected
   error. Fixed by reading STATUS **twice** — the first read checks the
   bits were set, the second checks the first read cleared them. M3 then
   dies on the second read.

   Smaller but concrete: M2 is **not** distinguished by the byte `0x5A`,
   which is bit-symmetric; it was killed by `0x01` → `0x80`. A stimulus
   set of only palindromic bytes would have let a bit-reversal bug
   through — an argument for the value-diversity coverpoint that is worth
   more than the abstract version.

3. **Toolchain fixes** (`tools/setup_iverilog.sh`). Every `make` first
   failed with `Makefile.icarus:53: *** Unable to locate command
   >iverilog<` in a shell where `iverilog -V` worked. Two root causes,
   both now fixed:
   - Shell functions are invisible to a child process doing its own
     command lookup. The script now also installs real wrapper **scripts**
     (carrying `-B`/`-M`) in `$IVERILOG_INSTALL_DIR/bin` and prepends it
     to PATH. This **supersedes the 2026-09-17 workaround** of calling the
     real binary by absolute path to use `timeout`: `timeout 150 vvp sim`
     now works, because `vvp` is a file.
   - `export -f iverilog vvp` actively **poisoned** cocotb's detection.
     cocotb's `Makefile.inc` sets `SHELL := bash`; `Makefile.icarus` does
     `CMD := $(shell :; command -v iverilog)` then `dirname $(CMD)`. In a
     bash that imported an exported *function* of that name, `command -v`
     prints the bare word `iverilog`, `dirname` yields `.`, and cocotb
     looks for `./iverilog`. The functions are no longer exported.
   Verified: both `phase4_uvm_milestone` and the older
   `phase4_uvm_python` now run with `make` after nothing but
   `source tools/setup_iverilog.sh` (sourced, not piped — the 2026-09-17
   gotcha still applies and is now in the script's header).

**The lesson worth carrying into Phases 5-6.** Two sessions running, the
bug has been in the *verdict*, not the checks. Generalised: **whenever
the subsystem that decides pass/fail is not the subsystem doing the
checking, the two must be wired together explicitly, and the wire must
itself be tested.** That covers a formal tool's exit code, a regression
runner parsing a log, and a coverage merge that silently drops a
database — not just this one cocotb/uvm-python combination. Mutation
testing is what surfaces it, because it is the only check that tests the
verdict rather than the design.

**Not yet covered (candidates for future runs):**
- **RAL basics** — now the ONLY remaining Phase 4 topic, and no longer
  abstract: the UART gives it a real six-register map, and the bus agent
  built today is exactly what a RAL model sits on top of. The obvious
  next session
- **Constrained-random and coverage-driven UART stimulus.** Today's
  stimulus is directed with hand-chosen values. The plan's Sections 2-3
  assign most features to CRV, and the M2/`0x5A` near-miss above is a
  concrete argument for randomised values feeding the existing
  coverpoints
- **vplan v2 revision** — now motivated from TWO independent directions:
  the RTL bring-up (2026-09-17) and the UVM environment's read-to-clear
  check (today). The "live status" wording cannot hold for the three
  STATUS error bits
- **Mutants not yet attempted**: the baud generator, the overrun path,
  the interrupt logic, the FIFO full/empty flags, the loopback mux. None
  of these has a check in the environment yet either, so they are
  simultaneously the next mutants and the next coverpoints. 5/5 is a
  claim about five defects, not about the DUT
- Code coverage measurement (plan Section 5 targets 95%) — still not
  attempted; Icarus has no native coverage support, so it needs its own
  toolchain investigation
- Phase 5 (SVA and formal) has not been started. Note that Icarus 10.3
  supports only a small SVA subset, so Phase 5 will likely need the same
  kind of toolchain decision Phase 4 needed on 2026-09-06

**Web search availability:** Not needed this session — the work was
building against an in-repo specification plus hands-on debugging, not a
literature review. No fetches attempted, so no access failures to record.

**Automation health:** **Push now works.** Unlike 2026-09-17, this
session's commits were pushed to GitHub and verified against the API, so
the credential problem recorded in the 2026-09-17 entry is resolved.
Unchanged: `git` still cannot run inside the connected folder (lock files
cannot be unlinked there), so work is done in the session's own scratch
clone. `scipy` remains absent from the device VM, and the
uvm-python/cocotb stack (`python-constraint --use-pep517`, `cocotb<2.0`,
`uvm-python`) has to be reinstalled each run, since the VM is rebuilt per
session. Both are per-run costs, not failures.

**Commits this run:** 4 (the UVM milestone environment + sim log +
mutation report; the setup_iverilog.sh toolchain fixes; the notes file;
progress.md). This AUTOMATION_LOG.md entry makes 5.

---

## 2026-09-19 — RAL closes Phase 4, and the mutation harness had the bug it exists to catch

**Status:** Full session. **Phase 4 is COMPLETE.** RAL basics was the last
remaining topic; the vplan v2 revision, open since 2026-09-17, is also
closed.

**Work done:**

1. **The register model** (`examples/phase4_ral/`, committed with its
   Makefile, mutation script, sim log and mutation report). A six-register
   `uvm_reg_block` for `rtl/uart_controller.v`, an 18-line
   `uvm_reg_adapter`, and a `uvm_reg_predictor` fed from the bus
   **monitor**, sitting on the 2026-09-18 APB-lite agent — which is
   *imported and reused unchanged*. That reuse is the argument for the
   layered architecture, so it was done rather than asserted.

   `auto_predict` is deliberately left OFF. Explicit prediction means the
   mirror moves only when the monitor **saw** the access, which is the
   same "never let the worker grade its own work" rule the last two
   sessions' findings came from, and here it is free. CHECK 1 proves it:
   a raw bus item that never touches the register object still moves the
   mirror, and moves it to **0x1B** for a write of 0xFB, because CTRL's
   reserved bits are modelled RO.

   **8/8 checks pass**, including both built-in generic sequences
   (`UVMRegHWResetSeq`, `UVMRegBitBashSeq`) — neither written for this
   UART, and between them they kill three of five mutants. That is the
   concrete answer to "what does a RAL buy".

   One debug cycle worth keeping: `uvm_reg.write()/read()/mirror()` take a
   `parent` that must be a **sequence**, because the map internally calls
   `rw.parent.start_item()`. Passing the test component gives
   `AttributeError: 'UartRalChecksTest' object has no attribute
   'start_item'`. The register layer sits on the sequence layer; it does
   not bypass it.

2. **Two registers the RAL cannot honestly model, excluded with reasons.**
   - **RX_DATA**: reading it pops the RX FIFO. No `uvm_reg` access policy
     expresses a side effect on state outside the register.
     `NO_REG_TESTS`, because a generic sequence reading it is silently
     consuming bytes another check is waiting for.
   - **STATUS**: four volatile live bits + three sticky read-to-clear
     error bits. `RC` models the error bits. The live bits are volatile —
     and **UVM does not COMPARE volatile fields**
     (`uvm_reg_field::configure` sets the compare mode to
     `UVM_NO_CHECK`), so a `hw_reset` sweep over STATUS reads it,
     compares nothing and reports success. A check that looks like a
     check and is not one, this time built into the *methodology*.
     STATUS's reset value (0x02) is therefore checked by hand, and
     **mutant M4 confirms that hand-written check is the only thing that
     catches a tx_full/tx_empty swap.**

3. **THE FINDING: the mutation harness had the bug it exists to catch.**
   The first run of `run_mutation_tests.sh` reported **0 killed, 5
   survived**. All five logs contained the correct `FAIL`. The script was
   trusting `make`'s exit status, and with cocotb 1.9.2 + Icarus 10.3
   `make` exits **0** even when cocotb prints `TESTS=1 PASS=0 FAIL=1`.
   Verified directly:

       $ make RTL_SRC=.../uart_controller_M3.v >/dev/null 2>&1; echo $?
       0

   This is the **third appearance of one defect class in this repo**:

   | Date | Verdict came from | Checking done by | Symptom |
   |---|---|---|---|
   | 2026-09-17 | the suite's own pass counter | checks that never executed | 55/55 against deliberately broken RTL |
   | 2026-09-18 | cocotb's PASS line | the UVM report server | `PASS=1` with UVM_ERRORs in the log |
   | 2026-09-19 | `make`'s exit code | cocotb's results line | every mutant reported as surviving |

   Each time the subsystem reporting the verdict was not the subsystem
   doing the checking, and nothing connected them. Today it was the
   harness whose entire purpose is to catch that — which is the strongest
   available argument that the rule generalises rather than being about
   one tool. The script now parses cocotb's own results line and
   distinguishes a third outcome, **NORESULT**, for a crash or compile
   error: a crash is not evidence that a check works, and counting it as
   a kill would be the same bug once more.

   **Action item for a future session:** `examples/phase4_uvm_milestone/`
   has a mutation *report* but no script. Whoever automates it must not
   use `make`'s exit code either.

4. **Mutation results: 5 killed, 0 survived, 0 no-verdict**, one mutant
   per targeted check (CTRL reserved bit readback; BAUD_DIV reset value;
   STATUS read-to-clear deleted; STATUS tx_full/tx_empty swapped;
   BAUD_DIV writes dropped). Two qualifications recorded in the report
   rather than glossed: **M2 is not a clean single-target mutant** —
   changing BAUD_DIV's reset value halves the baud rate, so it also trips
   CHECK 5 for an unrelated reason, which is collateral rather than extra
   confidence — and **5/5 is a claim about five defects in the register
   interface**, not about the DUT. Untouched: the baud generator, the
   TX/RX engines, FIFO full/empty, the interrupt OR, the loopback mux,
   and RX_DATA's pop-on-read, which is exactly the behaviour no access
   policy can express.

5. **vplan v2** (`verification_plans/uart_controller_verification_plan.md`).
   Open since 2026-09-17 and now forced from three directions. v1's
   blanket "live status" wording is not imprecise, it is
   **unimplementable** for the three error bits: a framing error lasts one
   stop bit, so a live frame_err would be clear before anything could read
   it, and the plan's own F4/F6 checks would be unobservable through a
   register read. New Section 1.1 re-specifies STATUS as two halves and
   states three consequences as requirements: reading STATUS is
   destructive; every error-bit check must read STATUS **twice**; and the
   volatile live bits mean a generic reset sweep checks nothing. New
   Section 1.2 covers RX_DATA's read side effect. **v1's text is
   annotated in place — nothing deleted** — and Section 7's now-historical
   paragraph is kept, because its closing prediction that bring-up would
   force a revision is what happened.

6. **Study notes**
   (`notes/2026-09-19-ral-register-model-and-the-harness-that-had-the-bug.md`),
   and **progress.md** updated: Phase 4 marked complete, with an explicit
   statement of what Phase 4 did *not* cover so it carries forward rather
   than disappearing behind a completed phase.

**Not yet covered (candidates for future runs):**
- **Phase 5 (SVA and formal) has not been started** — now the obvious
  next session, since Phase 4 is closed. Icarus 10.3 supports only a
  small SVA subset, so Phase 5 will need the same kind of toolchain
  decision Phase 4 needed on 2026-09-06 (SymbiYosys/Yosys is the
  candidate already named in the roadmap). Carry the verdict/checking
  rule in: a formal tool's exit code is the same shape as `make`'s
- **Constrained-random and coverage-driven UART stimulus.** All stimulus
  in all three benches is directed with hand-chosen values, while the
  vplan's Section 3 assigns most features to CRV. Still open, and now a
  capstone item rather than a Phase 4 gap
- **A mutation script for `examples/phase4_uvm_milestone/`** — it has a
  report but no runnable script, and whoever writes it must not use
  `make`'s exit code. New item created today
- **Code coverage measurement** (plan Section 5 targets 95%) — Icarus has
  no native support, so it needs its own toolchain investigation. Open
  since 2026-09-18
- **Mutants not yet attempted**: the baud generator, the overrun path,
  the interrupt logic, the FIFO full/empty flags, the loopback mux, and
  RX_DATA's pop-on-read. None has a check in any bench either, so they
  are simultaneously the next mutants and the next coverpoints
- **F7's baud-tolerance number** — never measured in any bench
- Phase 6: the capstone is now largely assembled out of Phase 4's parts;
  what is missing is the surrounding flow (lint, regression infra,
  coverage merge), CDC basics and the interview-prep pass

**Web search availability:** Not needed and not attempted — the work was
built against this repo's own RTL and vplan plus the uvm-python source,
which was read directly under
`~/.local/lib/python3.10/site-packages/uvm/reg/`. No fetches, so no access
failures to record.

**Automation health:** Device reachable, folder connected, push verified
against the GitHub API. Unchanged per-run costs: `git` still cannot run
inside the connected folder, so work is done in the session's own scratch
clone; the uvm-python/cocotb stack (`python-constraint --use-pep517`,
`cocotb<2.0`, `uvm-python`) is reinstalled each run because the VM is
rebuilt per session. One addition to the toolchain notes:
**`cocotb-config` installs to `~/.local/bin`, which is not on PATH in this
VM** — `export PATH="$HOME/.local/bin:$PATH"` is required before `make`,
or cocotb's Makefile include fails. `tools/setup_iverilog.sh` works as
fixed on 2026-09-18 (source it, do not pipe it).

**Commits this run:** 4 (the RAL example with its mutation script and
report; vplan v2; the notes file; progress.md). This AUTOMATION_LOG.md
entry makes 5. The RAL example went in as a single commit rather than
split into testbench / mutation harness, because the harness's first run
changed the testbench's own verdict logic and the two are not separable
after the fact.

---

## 2026-09-20 — Phase 5 started: an unbounded proof, and the verdict bug caught before it bit

Phase 4 closed on 2026-09-19, so this session started Phase 5 (Assertions &
Formal Verification). Three of its five checklist items are now done, two
partial with the reason stated.

1. **Toolchain decision, which 2026-09-19 flagged as Phase 5's first
   problem** (`tools/setup_formal.sh`). No root, VM rebuilt every session,
   so the oss-cad-suite tarball is not an option. `pip install --user
   yowasp-yosys z3-solver` gives the **real Yosys 0.69** plus SymbiYosys,
   `yosys-smtbmc` and `yosys-witness` as WebAssembly builds, and a native
   `z3` binary. One non-obvious step: sby calls its helpers as plain
   `yosys`/`yosys-smtbmc` while YoWASP installs them as `yowasp-*`, so the
   script drops shims into `$FORMAL_BIN`. The 2026-09-18 subshell gotcha
   carries over verbatim — **source it, do not pipe it**.

2. **Properties** (`rtl/uart_controller.v`, under `` `ifdef FORMAL ``). The
   TX/RX FIFO control path, chosen deliberately over the more
   interesting-looking serial datapath because its correctness is an
   *unbounded* claim — "the count never exceeds 8, on any trace of any
   length" — which is the one thing Phase 4's 60-check regression
   structurally cannot establish. P1 count range; P2 `(wptr − rptr) ==
   cnt[2:0]`, which is **not** implied by P1; P3 flag consistency; P4 the
   count changes by at most one per cycle and only as the strobes call for;
   C1 two cover statements.

3. **RESULT — an unbounded proof.** `bmc` depth 24 **PASS**; `prove`
   **PASS by temporal induction**, i.e. the invariants hold on every trace
   of every length, not merely to depth 24; `cover` **PASS** with both
   statements reached (full TX FIFO at step 10, wrapped read pointer at step
   6), so the suite is demonstrably **non-vacuous** — P1 and P2 would pass
   identically on a FIFO whose push guard was permanently false, and the
   covers are what rule that out.

4. **RESULT — five mutants, all five detected.** Defects injected into
   COPIES of the RTL: unguarded TX push (overflow), unguarded RX pop
   (underflow), count incrementing by 2, write pointer advancing by 2
   (which breaks **P2 only**, leaving P1 intact — the mutant that shows P2
   earns its place), and a wrong simultaneous-push-and-pop decrement.

5. **RESULT — the verdict-vs-checking defect class, FOURTH occurrence, and
   the first caught in advance.** `prove` mode has **three** outcomes, not
   two. Mutant M1 returns:

       engine_0.basecase:  Status: passed
       engine_0.induction: Status: failed
       DONE (UNKNOWN, rc=4)

   `UNKNOWN`, not `FAIL`. Induction starts from an *arbitrary*
   property-satisfying state, which may be unreachable, so a failed
   induction step is **not a counterexample** — it says only that the
   property is not k-inductive. The same mutant under `bmc` gives
   `DONE (FAIL, rc=2)` with a genuine reachable trace at P1 and P4. A
   harness scoring "prove did not return PASS" as a kill would claim a bug
   the tool never found, *and* would call a correct-but-not-k-inductive
   design broken. `run_formal.sh` scores **bmc FAIL** and prints the prove
   verdict as commentary. The three earlier occurrences (09-17 checks that
   never ran, 09-18 a PASS line ignoring UVM_ERRORs, 09-19 `make`'s exit
   code ignoring cocotb's FAIL) were all found *after the fact*; this one
   was recognised **before it produced a wrong number**, which is the first
   evidence the rule has actually been learned rather than merely logged.

6. **Measured, not assumed: sby's exit code is trustworthy.** Contrary to
   the pattern of the last three sessions, sby's exit code is informative
   (0 pass / 2 fail / 4 unknown) and agreed with its own status line in all
   13 runs. The script still parses the status line — and now *measures* and
   prints the agreement instead of assuming it either way. A second
   sub-finding worth keeping: `sby_verdict` is always called inside `$( )`,
   so any shell variable it sets dies with the subshell. The exit code and
   log are written to **files**. That is the same defect shape again, one
   layer down in bash.

7. **Two guards.** Stage 1 re-runs the Phase 4 60-check regression and
   requires **60/60** before any formal work, so "the `` `ifdef FORMAL ``
   block is invisible to Icarus" is checked rather than claimed — it
   reported 60 passed, 0 failed. Stage 4 deletes P1 and re-proves P2 to
   measure whether P1 is needed as a strengthening invariant: **it is not**,
   P2 is inductive alone. The negative result is recorded as measured rather
   than dropped, and it means the invariant-strengthening technique is
   studied but **unexercised** — an owed item, not a completed one.

8. **Study notes**
   (`notes/2026-09-20-sva-and-formal-bounded-vs-unbounded.md`) and
   **progress.md** updated. The notes state plainly which parts of SVA
   either available tool can run: **neither runs the concurrent-assertion
   sequence layer** (`##`, `[*]`, `|->`, local variables), so those are
   studied and not exercised, and the properties are written in the
   SymbiYosys immediate-assertion-on-a-clock-edge style. Writing SVA that
   was never executed would have looked better and meant less.

**Not yet covered (candidates for future runs):**
- **CSR properties on the six-register map** — the named next target.
  Short, shallow, exactly what BMC is good at; the 2026-09-19 RAL model
  already describes the map, and it overlaps vplan features F1/F1.1 that
  are currently covered only by directed simulation
- **A property that actually needs a strengthening invariant.** Stage 4
  found P2 inductive alone, so the technique remains unexercised. The
  serial datapath's "a started frame always completes" is the candidate
- **The SVA sequence layer** — not runnable on Icarus 10.3 or Yosys 0.69.
  Worth one session establishing whether any accessible tool (Verilator's
  partial SVA?) closes the gap, since interview questions assume fluency
- **`abc pdr` as a second engine** — computes invariants itself, and would
  give a check on the smtbmc result independent of the solver
- **The serial datapath under formal** — deliberately out of scope today:
  its properties span many bit periods (16·(BAUD_DIV+1) clocks each) and the
  WASM solver budget does not reach them at useful depth. A scope statement,
  not a claim that the datapath is correct
- **Constrained-random and coverage-driven UART stimulus** — all stimulus in
  all benches is still directed, while the vplan's Section 3 assigns most
  features to CRV. Open, a capstone item
- **A mutation script for `examples/phase4_uvm_milestone/`** — it has a
  report but no runnable script. Open since 2026-09-19
- **Code coverage measurement** (plan Section 5 targets 95%) — Icarus has no
  native support; needs its own toolchain investigation. Open since
  2026-09-18
- **Mutants not yet attempted**: the baud generator, the overrun path, the
  interrupt logic, the FIFO full/empty flags, the loopback mux, RX_DATA's
  pop-on-read. Today's five are all FIFO-control mutants
- **F7's baud-tolerance number** — never measured in any bench
- Phase 6: lint, regression infra, coverage merge, CDC basics, interview-prep

**Web search availability:** Not attempted. The toolchain question was
settled by trying the install directly, which is a stronger answer than
anything a search would have returned, and the rest was built against this
repo's own RTL.

**Automation health:** Device reachable, folder connected. Unchanged per-run
costs: git still cannot run inside the connected folder, so work is done in
the session's own scratch clone. New per-run cost: the formal toolchain
(`yowasp-yosys`, `z3-solver`) installs fresh each session like the
uvm-python stack, because the VM is rebuilt; `tools/setup_formal.sh` makes
that one command. The WASM builds print "Preparing to run … This might take
a while" on every invocation, but the full four-stage run — Icarus
regression, three proofs, ten mutant runs, one invariant experiment —
completes in well under two minutes.

**Commits this run:** 4 (the toolchain script; the formal property block
with its runner, configs, README and recorded output; the study notes;
progress.md). This AUTOMATION_LOG.md entry makes 5. The property block and
the runner went in as one commit rather than split, because the runner's
first M1 run changed how the harness defines detection and the two are not
separable after the fact — the same reason given on 2026-09-19.

## 2026-09-21 — Phase 5: the register map under formal, and a vacuity cover that certified its own uselessness

2026-09-20 named CSR properties on the six-register map as the next target.
Done, and the two things worth keeping from the session are both about
**vacuity** rather than about the register map.

1. **Nine CSR properties** (`rtl/uart_controller.v`, under a nested
   `` `ifdef FORMAL_CSR ``): C1 write/read-back on the three RW registers at
   their real widths (5, 8, 3 bits); C2 decode isolation; C3 read mux and
   reserved bits; C4 write-only and unmapped reads; C5 the four live STATUS
   bits; C6 sticky-error read-to-clear; C7 errors rise only in a stop state;
   C8 RX_DATA pop-on-read and no-pop-when-empty; C9 interrupt masking.

   **Nested under a second define on purpose.** The 2026-09-20 FIFO jobs pass
   `-DFORMAL` only, so they see exactly the source they saw then — and
   **Stage 4 re-runs all three of them and requires PASS** rather than
   asserting it. Stage 1 does the same one level down for the Phase 4 Icarus
   regression: **60/60**.

   The property worth memorising is **C2, stated in the contrapositive**: *a
   register that changed must have been addressed*. That is one line per
   register and it covers every "a write to STATUS / RX_DATA / any of the ten
   unmapped addresses must not disturb anything" requirement at once, instead
   of enumerating sixteen addresses. It also keeps covering them if a seventh
   register is added.

   C3 and C4 are labelled in the source as **structural restatements** —
   they say what the read mux says, so mutating the mux detects them
   trivially. Labelling the weak properties as weak is cheaper than
   discovering later that the suite's apparent breadth was mostly them.

2. **RESULT — the suite runs 15/15**
   (`examples/phase5_csr_formal/csr_formal_run_output_2026-09-21.txt`):
   regression guard 60/60; bmc depth 20 PASS; **prove PASS**; cover PASS with
   all seven covers reached; six of seven mutants detected; the seventh
   required to survive (below); and the three 2026-09-20 FIFO jobs still PASS.

3. **RESULT — a cover that passed by reading pre-reset state through
   `$past()`. Fifth occurrence of the verdict-vs-checking class, second
   caught before it produced a wrong number.**

   The vacuity cover for C6 was reported **reached at the earliest possible
   step**. Setting `overrun_err` needs a complete serial frame, so that was
   not credible and the witness trace was dumped instead of believed:

       step 0   f_past_valid=0  rst_n=0  overrun_err=1   <- solver's free choice
       step 1   f_past_valid=1  rst_n=1  overrun_err=0   <- reset has taken effect
                                paddr=0x1 psel=1 pwrite=0  (a STATUS read)

   This DUT has a **synchronous** reset. Step 0 precedes the first clock edge,
   so every register is the solver's to choose; `assume(!rst_n)` correctly
   forces reset at that edge but cannot un-choose step 0. `$past()` then
   **reaches back across the reset boundary** and returns the value the design
   had already thrown away.

   **Why it is worse than a mis-scored cover.** That cover's entire job was to
   show C6 was not vacuous. It passed without the design ever setting an error
   bit — a check whose only purpose is to detect false confidence, providing
   false confidence.

   **Scope, checked not assumed.** C1–C9 were unaffected: every assertion
   using `$past` is already guarded by `$past(rst_n)`. Only the covers lacked
   it — *a cover feels like a query and an assertion feels like an obligation*,
   and it is the same guard for the same reason. Fixed, plus a standing guard:
   the runner parses sby's per-cover "Reached cover statement in step N" lines
   and **fails the run if any cover is reached before step 2**. Earliest is
   now step 3.

   **New sub-lesson for the class:** a PASS whose *step number* is implausible
   is a finding. sby was truthful — the cover genuinely was reachable — and
   the conclusion drawn from it was wrong anyway. Four of the five occurrences
   so far were about a tool's output being misread, not about a tool lying.

4. **RESULT — two of the nine properties are vacuously true, and the vacuity
   is asserted rather than suspected.** `bmc` runs to depth 20; the only path
   that sets a sticky error bit runs through the RX engine completing a frame,
   **≈145 clocks even at `baud_div = 0`**. So C6's and C7's antecedents are
   never satisfiable in the bounded window.

   Stage 3b makes this a measurement: mutant **N5 disables the STATUS
   read-to-clear path entirely — exactly the defect C6 exists to catch — and
   the runner requires it to SURVIVE.** It does. A suite that cannot be broken
   by deleting the logic it is about is not testing that logic, and the
   difference between "C6 is proved" and "C6 is proved over traces reachable
   in 20 cycles, which never set an error bit" is the whole value of saying it.

5. **The attempt to close it, and what it cost.**
   `examples/phase5_csr_formal/uart_csr_deep_cover.sby` assumes the fastest
   legal baud and covers `rx_state == RX_STOP1`, `frame_err`, and a STATUS
   read following a set `frame_err`, at depth 170. **Measured: the WASM z3
   build reached step 61 of 170 in 2 min 39 s** and did not finish in budget;
   a second configuration was slower still. Committed for reproducibility, not
   part of the default run. This is a statement about the solver budget, not
   the design — the Phase 4 simulation regression sets all three error bits
   every run.

   **The resulting scope line matches 2026-09-20's from the other side.** Day
   1 put the serial datapath out of formal scope because its properties span
   many bit periods. Day 2 arrives at the same boundary from the register
   side: **any property whose antecedent needs a complete UART frame is out of
   reach for bounded model checking on this toolchain and belongs to
   simulation.** Knowing where that line falls, and which of one's own
   properties sit on the wrong side of it, is the output a PASS/FAIL summary
   cannot give.

6. **Mutation, seven defects.** N1 write-decode aliasing onto STATUS (C2);
   N2 CTRL reserved bits reading 1 (C3); N3 unmapped reads returning 0xFF
   (C4); N4 STATUS `tx_full`/`tx_empty` swapped (C5); N5 read-to-clear
   disabled (survives, §4); N6 RX_DATA popping an empty FIFO (C8); N7 the
   TX-empty interrupt ignoring its mask (C9). **N6 fails at both line 433 —
   the 2026-09-20 FIFO property P4 — and line 608, C8.** Two independent
   suites catching one defect from different directions is the cheapest
   evidence available that neither is self-fulfilling.

7. **Study notes**
   (`notes/2026-09-21-csr-formal-properties-and-bounded-vacuity.md`): the
   seven reusable CSR obligations written out as properties (§2), both
   findings (§3, §4), and a generalisation worth carrying to any block (§5) —
   **three distinct ways a passing property can mean nothing**: antecedent
   never satisfied, cover reached from an unreachable state, and property =
   the logic written twice. A fourth, over-constrained `assume()`, is the
   shape of the deep-cover job's own baud assumption, which is why that
   assumption lives in its own `ifdef` and its own job.

8. **progress.md** — the "practical formal use cases" item is closed, with
   both caveats stated in the checklist itself rather than only in the notes.

**An owed item created today:** **reset-value properties are unchecked.** The
seven CSR obligations include reset value, and the `f_past_valid` idiom that
makes every other property well-formed disables everything *during* reset, so
the reset values themselves are never asserted. A separate job with the
opposite guard closes it.

**Not yet covered (candidates for future runs):**
- **Reset-value properties** — created today, and the natural next item: it is
  the one CSR obligation of the seven this suite does not check, it is cheap,
  and it needs a guard that is the mirror image of the one everything else uses
- **A property that actually needs a strengthening invariant.** 2026-09-20's
  stage 4 found P2 inductive alone and today's properties are all shallow, so
  the technique is still studied and unexercised. The serial datapath's "a
  started frame always completes" remains the candidate
- **`abc pdr` as a second engine** — a solver-independent check, and now also
  the obvious candidate for the deep-cover job smtbmc cannot finish
- **The SVA sequence layer** (`##`, `[*]`, `|->`, local variables) — runnable
  on neither tool here; worth one session establishing whether anything
  accessible closes the gap, since interviews assume fluency
- **Constrained-random and coverage-driven UART stimulus** — all stimulus in
  all benches is still directed while the vplan assigns most features to CRV.
  The capstone item
- **A mutation script for `examples/phase4_uvm_milestone/`** — it has a report
  but no runnable script. Open since 2026-09-19
- **Code coverage measurement** (plan Section 5 targets 95%) — Icarus has no
  native support. Open since 2026-09-18
- **Mutants not yet attempted**: the baud generator, the overrun path, the
  interrupt *enable* combinations, the loopback mux. Today added the register
  file and the interrupt mask to the covered set
- **F7's baud-tolerance number** — never measured in any bench
- Phase 6: lint, regression infra, coverage merge, CDC basics, interview-prep

**Web search availability:** Not attempted. Everything this session needed was
either in the repo's own RTL or answerable by running the tool, which is a
stronger answer than a search result.

**Automation health:** Device reachable, folder connected. Unchanged per-run
costs: git cannot run inside the connected folder, so work happens in the
session's scratch clone; the formal toolchain reinstalls each session via
`tools/setup_formal.sh`. New measurement: the full four-stage CSR run —
Icarus regression, three proofs, seven mutant jobs, one expected-survival job,
three FIFO re-runs — is 15 sby invocations and completes in about a minute.

**Commits this run:** 3 (the property block with its runner, configs, README
and recorded output; the study notes; progress.md). This AUTOMATION_LOG.md
entry makes 4. The property block and the runner went in together, as on
2026-09-19 and 2026-09-20, because the runner's first cover run is what
changed the property block — the two are not separable after the fact.

## 2026-09-22 — Reset values proved, and a property measured to be doing nothing

**Open item closed:** "**Reset-value properties**" — created 2026-09-21 and
named there as *the natural next item*: one of the seven CSR obligations, and
the only one the day-2 suite did not check.

**Result:** `examples/phase5_csr_formal/run_reset_formal.sh`, five stages,
**15 passed, 0 failed** (`reset_formal_run_output_2026-09-22.txt`).

1. **Why the gap was structural.** Every formal property in this repo — the
   2026-09-20 FIFO invariants and the 2026-09-21 CSR properties alike —
   opens `if (f_past_valid && rst_n)`. That is the standard SymbiYosys idiom
   and it is correct: a steady-state property has nothing to say while the
   design is being forced to a known state. It also means **the entire reset
   window is excluded from every property in the suite**, and the
   reset-value obligation is the one whose whole content lives inside it.
   The gap was not a missing test — it was **a correct convention, uniformly
   applied, with a blind spot**, which is harder to see precisely because
   the convention is right everywhere it was used.

   The fix is the mirror image, `(f_past_valid && !$past(rst_n))`, in its own
   `` `ifdef FORMAL_CSR_RESET `` so the day-1 (`-DFORMAL`) and day-2
   (`-DFORMAL -DFORMAL_CSR`) jobs keep seeing bit-identical source.

2. **`$past` is safe here and was not on 2026-09-21 — the distinction is
   worth stating.** Day 2's bug was a cover reading *state* across the
   synchronous-reset boundary, state the reset had already discarded. R1–R4
   read `$past(rst_n)` — the **reset signal**, not state. Reading the reset
   signal across that boundary is the *point*; reading state across it was
   the bug. The two look identical in the source and are opposite in
   meaning. Also: the reset is synchronous, so the obligation is "one edge
   *after* `rst_n` was sampled low", not "whenever `rst_n` is low" — the
   obvious wording describes an asynchronous reset and would **fail on
   correct RTL**.

3. **The four properties.** R1: 28 architectural registers at their reset
   values, transcribed from the RTL's reset clauses so a register added later
   without a property shows up as a diff. R2: the *read port*, which is the
   obligation a CSR spec actually states — `prdata` is a combinational mux,
   so a decode fault can leave every register correctly reset and still
   return the wrong value, which R1 cannot catch. R3: `irq` low out of reset
   (a core asserting `irq` before software enables anything takes a spurious
   interrupt on every boot). R4: reset dominates a concurrent bus write.

   **`STATUS` resets to `8'h02`, not `8'h00`** — bit 1 is `tx_empty`, a live
   decode of `tx_cnt == 0`, which reset makes true. "Registers reset to zero"
   is the default assumption and it is wrong here; the constant was derived
   from the RTL's own concatenation *in the comment, where a reviewer can
   check it*, rather than assumed. That is day 2's third self-fulfilment
   shape, avoided deliberately.

4. **One register deliberately out of scope, and the omission proved rather
   than described.** `ADDR_RX_DATA` reads `rx_fifo[rx_rptr]` and the FIFO
   array has **no reset clause** — a real design decision (eight bytes
   unreadable through the protocol while `rx_cnt == 0`), so asserting a value
   would assert something false. **Mutant M7 corrupts exactly that storage at
   reset and is REQUIRED TO SURVIVE.** Same discipline as day 2's N5.

5. **Mutation: six detected.** M1 CTRL not cleared; M2 TX line idles low;
   M3 a concurrent write beats reset; M4 `tx_cnt` resets to 1 so
   `STATUS.tx_empty` is wrong; M5 `frame_err` resets *set*; M6 `irq` ignores
   its enable mask (R3-only — R1 and R2 are untouched by it). Every mutant is
   `cmp`'d against the original first, so **a `sed` that matched nothing is a
   FAIL, not a silent pass** — the 2026-09-18 green-regression-that-wasn't
   guard, now standing.

6. **THE FINDING — R4 is measurably redundant, and that is a FOURTH way a
   passing property can mean nothing.** Day 2 generalised to three shapes:
   antecedent never satisfiable; cover reached from an unreachable state;
   property = the logic written twice. **R4 fails none of the three.** Its
   antecedent is satisfiable (cover `C_R2`, reached at step 4), it is a true
   statement about real behaviour, and it restates no RTL line.

   Stage 5 measures it anyway, **by deletion**: rebuild the RTL with R4
   removed, and again with *only* R4 kept, and run M3 — the defect R4 was
   written for — against both.

   ```
   noR4:   clean=PASS   with-M3=FAIL
   onlyR4: clean=PASS   with-M3=FAIL
   ```

   **Both detect it.** R1 asserts the reset values *unconditionally*, so the
   concurrent-write case was already inside R1. R4 changes no verdict
   anywhere in the suite, and no mutant can distinguish them unless R1 is
   narrowed.

   Vacuity asks whether a property is ever *evaluated*; **subsumption asks
   whether, having been evaluated, it ever changes a verdict.** All three
   vacuity tests pass on R4 and all three are blind to this. Only a deletion
   experiment finds it, and a deletion experiment is in no standard flow.

   R4 is **kept and annotated in place**, not deleted: it states an intent
   (reset has priority over the bus) that R1 only implies, and it would earn
   its detection power the moment R1 were narrowed to a quiet bus — which is
   how a larger design has to write R1, because enumerating every register
   unconditionally does not scale.

   **Transferable rule, and the first technique in this repo that can say a
   suite is LARGER than it needs to be** — every previous one could only say
   it was smaller than it looked: *a property earns its place by changing a
   verdict somewhere; if no mutant distinguishes it, say so in the file.*
   Mutation coverage attributed to **individual** properties, by deletion, is
   the property-level analogue of code coverage and costs one variant per
   property. Interview framing for "how do you know your assertions are
   pulling their weight?": bad answer, count them; standard answer, mutation
   coverage of the suite; better answer, per-property mutation coverage.

7. **Scope, stated rather than implied.** BMC to depth 12 — reset properties
   are shallow by construction, so depth is not the binding constraint it was
   on day 2, and no k-induction is claimed. Power-on reset **and** a reset
   that returns after the design has run are both covered (`C_R1`, step 3).
   **A reset asserted mid-frame is NOT covered**: reaching a frame is ~145
   clocks — the same solver-budget boundary day 1 hit from the datapath side
   and day 2 from the register side, now met from a third direction.

8. **Guards that held.** Stage 1 re-ran the Phase 4 bench: **60/60**, so "the
   new `` `ifdef `` is invisible to Icarus" is checked, not asserted. Both
   new covers reached at steps 3 and 4, clearing the step-≥2 guard added
   2026-09-21. Stage 4 re-ran the 2026-09-20 FIFO job and all three
   2026-09-21 CSR jobs: **all four still pass**.

**Not yet covered (candidates for future runs):**
- **Per-property mutation coverage for the whole suite** — created today and
  the **top** item. Stage 5 applied the deletion experiment to exactly one
  property because that is the one it suspected. The 2026-09-20 FIFO
  invariants (P1–P4) and the 2026-09-21 CSR properties (C1–C9) have **never**
  been asked whether any of them is subsumed, and today's result says the
  question has a non-trivial answer. It is cheap and mechanical
- **A property that actually needs a strengthening invariant.** 2026-09-20's
  stage 4 found P2 inductive alone, today's are shallow by construction, so
  the technique remains studied and unexercised. The serial datapath's "a
  started frame always completes" is still the candidate
- **`abc pdr` as a second engine** — a solver-independent check, and still
  the obvious candidate for the deep-cover job smtbmc cannot finish
- **A reset asserted mid-frame** — created today. It needs the same ~145-clock
  reach as day 2's deep cover, so it is blocked on the same budget and is a
  reason to try `abc pdr` rather than a separate item
- **The SVA sequence layer** (`##`, `[*]`, `|->`, local variables) — runnable
  on neither tool here; worth one session establishing whether anything
  accessible closes the gap, since interviews assume fluency
- **Constrained-random and coverage-driven UART stimulus** — all stimulus in
  all benches is still directed while the vplan assigns most features to CRV.
  The capstone item, and now the longest-standing one
- **A vplan v2 revision** — the 2026-09-17 bring-up found the plan's "live
  status" wording cannot hold for the three STATUS error bits. Still open,
  and today adds a second correction it should carry: the vplan says nothing
  about reset values, which are now formally proved
- **A mutation script for `examples/phase4_uvm_milestone/`** — it has a
  report but no runnable script. Open since 2026-09-19
- **Code coverage measurement** (plan Section 5 targets 95%) — Icarus has no
  native support. Open since 2026-09-18
- **Mutants not yet attempted**: the baud generator, the overrun path, the
  interrupt *enable* combinations, the loopback mux
- **F7's baud-tolerance number** — never measured in any bench
- Phase 6: lint, regression infra, coverage merge, CDC basics, interview-prep

**Web search availability:** Not attempted. Everything this session needed was
in the repo's own RTL or answerable by running the tool — which, as on
2026-09-21, is a stronger answer than a search result.

**Automation health:** Device reachable, folder connected, 10:30 UTC firing;
neither repo had a 2026-09-22 entry, so a full session was run. Unchanged
per-run costs: git cannot run inside the connected folder, so work happens in
the session's scratch clone; the formal toolchain reinstalls each session via
`tools/setup_formal.sh` (source it, do not pipe it). New measurement: the
five-stage reset run — Icarus regression, two sby proofs, seven mutant jobs,
four cross-check jobs and four redundancy variants — is 17 sby invocations
and completes in about 90 seconds.

**Commits this run:** 3 (the property block with its runner, configs, README
and recorded output; the study notes; progress.md). This AUTOMATION_LOG.md
entry makes 4. The property block and the runner went in together, as on
2026-09-19, -20 and -21, because stage 5's deletion experiment is what
changed the property block — R4's annotation did not exist until the runner
measured it, and the two are not separable after the fact.

---

## 2026-09-23

**Status:** Automated session, Phase 5 day 4. The top item of 2026-09-22's
"Not yet covered" list, taken verbatim: per-property mutation coverage for
the whole suite.

**Work done:**

1. **The harness** (`examples/phase5_property_coverage/`). 2026-09-22
   deleted one property and asked whether any verdict changed. This does it
   for all **17** properties of all three suites — **252 `sby` invocations,
   about twelve minutes** — in three phases, each answering what the
   previous one could not:

   | phase | experiment | distinguishes |
   |---|---|---|
   | 1 | delete one property, re-run every mutant | does it ever change a verdict? |
   | 2 | keep one property as the **only** live one | SHADOWED vs UNEXERCISED |
   | 3 | inject the defects the unexercised ones were written for | hole closed, shadowed after all, or escape |

   **Phase 2 is the point, and the reason phase 1 alone would have been
   wrong.** "Deleting it changes nothing" is two opposite situations wearing
   one result: the property *can* detect something and is merely shadowed,
   or it detects *nothing* — which is a fact about the **mutant set**, not
   about the property. Collapsing them would recommend deleting a property
   whose real problem is that nobody ever tested it.

2. **RESULT — 9 load-bearing, 4 shadowed, 4 unexercised.**
   Load-bearing: P1, P2, C2, C3, C4, C5, C9, R1, R3. Shadowed: P4, C8, R2,
   R4. Unexercised: P3, C1, C6, C7.

3. **CONTROL, and the reason any of this is believable.** The harness must
   independently reproduce the one answer already known. Phase 1 reproduces
   2026-09-22's hand-built R4-is-subsumed; phase 2 reproduces its finer
   form — R4 detects K1, K3 and K4 alone and none of them uniquely. Both
   pass. A harness that disagreed with the known answer would not be worth
   listening to about the sixteen new ones.

4. **RESULT — cross-suite subsumption, which the single-property experiment
   structurally could not see.** The CSR job compiles `-DFORMAL
   -DFORMAL_CSR` and the reset job `-DFORMAL -DFORMAL_CSR_RESET`, so **both
   silently carry the 2026-09-20 FIFO invariants**. C8 comes back shadowed,
   and what shadows it is P1/P2 from a *different day's suite* catching the
   same underflow first. General form worth carrying: **a property's
   redundancy is a property of the COMPILE, not of the suite it was written
   in.**

5. **RESULT — two holes closed, and C1 had been advertising its own.** C1's
   comment says verbatim *"a width mutation is exactly what this catches"*,
   and no width mutation had ever been injected. N8 (the INT_EN write drops
   its top bit) is detected and **missed** with C1 deleted. Same shape for
   P3 with M6 (`tx_full` computed from the empty constant, so full and empty
   coincide). Two of the four unexercised properties were one mutant away
   from being the only thing standing between the design and a defect.

6. **A CORRECTION made inside the session, and the more useful finding.**
   N9 (a STATUS read that no longer clears `frame_err`) escapes the whole
   suite, and the first write-up called that a **fifth** way a passing
   property can mean nothing. **It is not.** 2026-09-21 established exactly
   this, by exactly this method: stage 3b of `run_csr_formal.sh` injects N5,
   disables the read-to-clear path entirely and *requires the mutant to
   survive*, with the ~145-clocks-against-depth-20 argument written out
   beside it. N9 is N5 in a different disguise; the escape is plain bounded
   vacuity, class 1 since 09-21. The overclaim is annotated in place in the
   note, the README and the RTL rather than deleted, because **the lesson is
   that a mechanical sweep over seventeen properties re-derives what the
   repo already knows and presents it with exactly the same confidence as
   what it does not.**

   What survives as new is the **N10 control**. N5 shows C6 cannot be broken
   at this depth; it does not show C6 is any good, because a syntactically
   empty property would survive N5 identically. N10 makes a STATUS read
   *set* `frame_err` — three steps, no RX activity — and C6 and C7 both fail
   it at step 3. The pair separates *"antecedent unreachable"* from
   *"antecedent unreachable **or** property empty"*, which one survivor
   mutant cannot, and it costs one mutant.

7. **The bug the guards caught.** The FIFO suite's cover block is **also
   called `C1`**, inside `` `ifdef FORMAL ``. A bare banner search for
   `// ---- C1` found that one instead of the CSR property and deleted
   across two `` `endif ``s; the job returned `ERROR: Found \`endif outside
   of macro conditional branch`, and guard G3 (drop-one must still PASS on
   clean RTL) scored the row INCONCLUSIVE rather than letting it read as
   "redundant". `span()` is now region-aware. **A name collision between two
   suites is invisible until something addresses properties by name**, and
   nothing in a normal flow ever does — it existed for three days and cost
   nothing until a script tried to talk about "C1".

8. **Nothing was deleted.** P4, C8, R2 and R4 are annotated in place with
   the reason each is kept (P4 is the only property constraining the *rate*
   of change; C8 would earn its place in a job built without `-DFORMAL`; R2
   is the only protocol-level statement of the reset values; R4 states an
   intent R1 only implies). C6 and C7 — which look, in the raw phase-1
   matrix, like the two most obviously deletable properties in the repo —
   are guarding a real defect the bound cannot reach, and N10 shows they
   will catch it the day it becomes reachable.

9. **Guards that held.** All five `sby` jobs re-run after the RTL comment
   edits: `uart_fifo_bmc`, `uart_fifo_prove`, `uart_csr_bmc`,
   `uart_csr_prove`, `uart_reset_bmc` — all PASS. Phase 4 Icarus bench still
   **60/60**. G1 (baseline clean PASS) and G2 (every baseline mutant
   detected) held for all three suites: 5/5, 6/6, 6/6.

**Not yet covered (candidates for future runs):**
- **Constrained-random and coverage-driven UART stimulus** — all stimulus in
  all benches is still directed while the vplan assigns most features to
  CRV. Now the **top** item and the longest-standing one: today closed the
  last of the mechanical property-quality questions, and what is left is the
  capstone
- **`abc pdr` as a second engine** — promoted by today's work rather than
  merely still open. Three of the four things this repo cannot currently say
  (a reset asserted mid-frame, the deep cover, and now the N9/N5 escape) are
  the same ~145-clock reach against a bounded engine. A solver that does not
  need the bound would collapse three open items into one experiment
- **A vplan v2 revision** — the 2026-09-17 bring-up found the "live status"
  wording cannot hold for the three STATUS error bits; 2026-09-22 added that
  the plan says nothing about reset values; today adds a third correction it
  should carry, that the plan assigns C6/C7's behaviour to formal while
  formal provably cannot reach it at any depth this toolchain can run
- **Per-property coverage of the PHASE 4 UVM environment** — created today.
  The technique is now scripted and the UVM milestone has a mutation report
  but no per-component attribution, so the same question ("which component
  of the environment would notice if it were removed?") is one adaptation
  away
- **Mutants not yet attempted**: the baud generator, the overrun path, the
  interrupt *enable* combinations, the loopback mux. Today added three
  (N8, N9/N10, M6) and each one changed a verdict, which is an argument for
  writing more of them rather than more properties
- **A property that actually needs a strengthening invariant** — still
  studied and unexercised; the serial datapath's "a started frame always
  completes" remains the candidate, and it is blocked on the same bound
- **The SVA sequence layer** (`##`, `[*]`, `|->`, local variables) — runnable
  on neither tool here; worth one session establishing whether anything
  accessible closes the gap, since interviews assume fluency
- **A mutation script for `examples/phase4_uvm_milestone/`** — it has a
  report but no runnable script. Open since 2026-09-19
- **Code coverage measurement** (plan Section 5 targets 95%) — Icarus has no
  native support. Open since 2026-09-18
- **F7's baud-tolerance number** — never measured in any bench
- Phase 6: lint, regression infra, coverage merge, CDC basics, interview-prep

**Web search availability:** Not attempted. Everything this session needed
was in the repo's own RTL and scripts — and finding 6 is a reminder that
reading the repo's own earlier scripts is the search that mattered.

**Automation health:** Device reachable, folder connected; neither repo had a
2026-09-23 entry, so a full session was run. The session VM restarted once
mid-run (between the two repos) and `$HOME/work` survived it, but installed
pip packages did not — the formal toolchain reinstalls per session anyway
via `tools/setup_formal.sh` (source it, do not pipe it). **New constraint
measured today:** background jobs do NOT survive between automation shells,
so a `nohup ... &` sweep is silently killed the moment the call returns.
`run_chunk.sh` is written around that: it records each verdict as it lands,
never re-runs a completed variant, and stops at a deadline, so the 252-job
sweep completes over three or four calls instead of one long one.

**Two further operational findings, both from the VM restart:**

1. **The push recipe's `shred -u /tmp/.tok` can FAIL after a restart.** Files
   written to the VM's `/tmp` before the restart come back owned by
   `nobody:nogroup`, so the post-push cleanup returns
   `rm: Operation not permitted` and a 0600 token copy is left behind. It is
   unreadable by the session uid and the VM is ephemeral, so nothing leaks,
   but the cleanup step cannot be assumed to have worked. **Use `mktemp` for
   the token and the askpass helper rather than fixed names** — a fixed name
   also collides with the pre-restart file and makes the *write* fail with
   `Permission denied`, which is how this was found: the second push of the
   session could not create `/tmp/.tok` at all.

2. **A committed file can revert in the WORKING TREE across the restart.**
   After the restart, `git status` in the graphene repo showed
   `AUTOMATION_LOG.md` modified with the day's 179-line entry *removed* —
   the commit and the pushed remote were both intact, only the checked-out
   file was stale. `git checkout -- <file>` restores it. The lesson for a
   future run: **after any restart, check `git status` in every clone before
   trusting the working tree**, and verify against the remote rather than
   against the local file.

**Commits this run:** 5 (the harness with its four scripts and recorded
output; the RTL annotations; the in-session correction across note, README
and RTL; the study notes; progress.md). This AUTOMATION_LOG.md entry makes
6. The correction is its own commit rather than folded into the note,
because a claim that was wrong for four commits and then fixed should be
visible as that in the history.

---

## 2026-09-24 — Constrained-random and coverage-driven UART stimulus: the top item closed, a measured 7.3x, and two findings about the coverage model itself

**Status:** Automated session. Live web search **not used** — everything this
session needed was the repo's own RTL, its vplan and Icarus. Took the top item
of 2026-09-23's list verbatim: *"Constrained-random and coverage-driven UART
stimulus — all stimulus in all benches is still directed while the vplan
assigns most features to CRV. Now the top item and the longest-standing one."*

**What was built.** `examples/phase6_crv_uart/` — `uart_crv_cov_tb.v` (a
constrained-random, coverage-driven, self-checking loopback bench),
`run_crv_cov.sh` (the closure sweep) and `run_mutation_tests.sh`, with all
three outputs recorded.

Icarus 10.3 has no `rand`, no `constraint` blocks, no `covergroup` and no
`solve … before`, so both mechanisms are written out in Verilog-2001. **That
is the pedagogical value, not a workaround:** a constraint solver written by
hand is rejection sampling over a bounded budget, a covergroup written by hand
is counter arrays plus a sampling point plus a closure predicate, and a
coverage-driven flow written by hand is a mapping from *unhit bin* back to
*stimulus that hits it*. The third is the one interviews probe, and doing it
by hand makes the answer concrete: the tool does not invent stimulus, it
searches the constraint space with the coverage database as its objective.
Everything else the engineer writes either way.

1. **The rejection budget is a real guard, not decoration.**
   `pick_config_random` counts rejected candidates and **fails the run** past
   200 in a single draw — the hand-built equivalent of a solver reporting an
   unsatisfiable constraint set. Without it an over-constrained draw is an
   infinite loop, and **an infinite loop is the one failure mode a regression
   cannot report**. Measured on a random run: 309 rejections total, worst
   single draw 11. `C2` (`baud_div <= 3`) is drawn from 0..7 deliberately so
   the rejection count is a real number; a constraint that never rejects is
   untested machinery.

2. **RESULT — the measured cost of not steering, over 8 seeds, same
   constraints and same seeds.** Transactions to closure of all 30 bins:

   | | random | steered | ratio |
   |---|---|---|---|
   | mean | 340.8 | 46.9 | **7.3x** |
   | worst seed | 643 | 60 | **10.7x** |
   | best seed | 105 | 36 | 2.9x |
   | spread (max/min) | **6.1x** | **1.7x** | — |

   **The spread is the result.** Steering improves the worst case 10.7x and
   the best 2.9x, collapsing a 6.1x seed-to-seed spread to 1.7x. So the honest
   claim is not "coverage-driven stimulus is 7x faster" but **"coverage-driven
   stimulus makes closure predictable"**, and on a real project that is the
   more valuable of the two because a regression budget is set by the worst
   case. Seeds 5 and 6 give 2.0–2.1x: a session that had run one seed and
   drawn seed 5 would have recorded a true number that misrepresents the
   mechanism by a factor of five. Same lesson as the graphene repo's
   2026-09-20 unrepresentative-sample finding, reached from the other side.

3. **FINDING — a coverage hole can be a SAMPLING-POINT defect, and in the
   report it is indistinguishable from a stimulus gap.** The first working
   bench closed 29/30, missing `cp_txq.full`. The natural reading — the
   stimulus never fills the TX FIFO — was wrong. The push loop samples STATUS
   *before* each push, so with `burst_len = 8` its last sample sits at
   occupancy 7 while the FIFO reaches 8 immediately afterwards. The stimulus
   created the state and the covergroup never looked. One extra sample after
   the push loop closed it. `full = 0` in a report cannot distinguish "never
   happened" from "never sampled", and the two have completely different
   fixes. It was caught **because closure is a pass criterion** — as a report
   line, "29/30" beside a PASS reads as "nearly closed" and gets carried for
   weeks.

4. **FINDING — the closure counter and the closure criterion were reading
   different databases. Sixth occurrence of the verdict-vs-checking class
   (09-17, 09-18, 09-19, 09-20, 09-21), and the first found by two outputs of
   one run disagreeing.** `seed=6, steer=1` printed both
   `TRANSACTIONS TO CLOSURE : NOT REACHED in 60` and
   `RESULT: PASS (11460/11460 checks)`. The criterion called `bins_hit()` at
   the end; the counter updated only at *push* sites; seed 6's last bin was
   filled by a STATUS sample. **The bench had closed and reported that it had
   not.** Every coverage update now routes through one `note_closure` task,
   so there is one definition of closure — and the bench now asserts that its
   two statements about closure agree. Two lines. **An inconsistency between
   two outputs of one run is the cheapest bug detector available: no reference
   model, no golden file, no second tool.** Worth looking for anywhere a bench
   states the same fact twice.

5. **RESULT — mutation testing: 6 injected, 4 detected, 2 escaped, 6/6
   verdicts as predicted in advance.** Every mutant goes into a **copy** of
   the RTL under `/tmp`; the repo's RTL is never touched. G1 requires the
   baseline to PASS and aborts otherwise, because a baseline that does not
   pass makes every row meaningless. Following 2026-09-19's rule, the script
   scores prediction against outcome rather than a detection count.

   Detected: M1 TX parity polarity swapped (RX parity check disagrees and
   sets `parity_err`, which every status read asserts clear); M2 RX data bit
   inverted at the mid-bit sample; M3 `CTRL.stop_bits` ignored by TX (a
   two-stop frame runs one bit short, so the next start bit lands inside the
   previous frame's stop window); **M4 TX FIFO count never increments**.

6. **M4 is the session's best argument for its own design decision.** Under
   M4 every byte still arrives correctly and every data check passes; what
   breaks is that `tx_full` can never assert, so `cp_txq.full` becomes
   unreachable and **closure fails**. **M4 is caught by the coverage
   criterion and by no data check whatever.** Closure-as-pass-criterion
   catches a class of RTL defect that no amount of self-checking stimulus
   reaches — which is exactly the kind of claim this repo has previously had
   to take on faith.

7. **M5 is the most useful row in the table, and it is an escape.**
   `BAUD_DIV` ignored by the baud generator: **escaped, predicted.** In
   loopback the TX and RX engines **share one baud generator**, so a wrong
   divisor desynchronises nothing — both sides are wrong together and the data
   is perfect. **No loopback bench, at any level of sophistication, can detect
   a baud-rate error.** That is structural rather than a gap in this suite,
   and it converts the long-open *"F7's baud-tolerance number, never measured
   in any bench"* item from "write more stimulus" into a specific argument for
   the **standalone RX bit-driver** the Phase 4 milestone still has open: only
   a driver with its own timebase can measure F7 at all. M6 (STATUS read no
   longer clears the sticky bits) also escaped as predicted — a clean loopback
   burst never injects an error, so a bit that fails to *clear* is never
   observed *set*.

8. **One guard against the mutation harness itself.** The script fails the
   run if an injection matched nothing. A `sed` that silently misses leaves
   the RTL unmodified and the row scores as an escape against **correct**
   RTL — the same class of false verdict the mutation test exists to prevent,
   one level up. This is the 2026-09-23 `span()`/`C1` name-collision lesson
   applied before it cost anything.

9. **One load-bearing implementation detail, recorded because getting it
   wrong made a bin unreachable.** The TX FIFO is filled with `CTRL.en = 0`.
   `tx_push` does not depend on `en`, but the TX engine only pops in
   `TX_IDLE` when enabled, so with `en = 1` the first byte drains within a few
   cycles of the first push and `tx_cnt` never reaches 8 — making
   `cp_txq.full` unreachable and the closure criterion permanently
   unsatisfiable. A coverage model can be written so that the DUT cannot
   satisfy it, and the bench then fails forever for a reason that looks like
   a DUT bug.

**Methodological note.** Findings 3 and 4 are both about the *coverage model*
rather than the stimulus or the DUT, and together they make a point the repo
has not recorded before: **a covergroup is a measuring instrument, and an
instrument can be miscalibrated in ways that look exactly like a result.**
Finding 3 is a mis-placed sampling point reading as a stimulus gap; finding 4
is two readouts of one instrument disagreeing. Five of the repo's six
verdict-vs-checking occurrences were about *checkers*; this is the first pair
about *measurement*, and the detectors are different — a reachability argument
for the first, a cross-check between two outputs for the second.

**Not yet covered (candidates for future runs):**
- **Constrained-random stimulus driven at the RX PIN, from an independent
  timebase** — created today by M5 and now the **top** item. It is the only
  thing that can measure F7's baud tolerance, and it is also what would make
  framing errors, parity errors and overrun reachable outside the directed
  bring-up bench. It subsumes the standalone RX bit-driver item that has been
  open since the Phase 4 milestone
- **`abc pdr` as a second engine** — unchanged from 09-23 and still the best
  single experiment available: three of the things this repo cannot say are
  the same ~145-clock reach against a bounded engine
- **A vplan v2 revision** — now carries four corrections it should absorb:
  the "live status" wording (09-17), silence on reset values (09-22), C6/C7's
  behaviour assigned to formal where formal provably cannot reach it (09-23),
  and today's, that Section 3's CRV assignment is satisfiable for the register
  interface and the loopback datapath but **not** for F7, for a structural
  reason the plan does not mention
- **Per-property coverage of the PHASE 4 UVM environment** — open since
  09-23; the technique is scripted and the UVM milestone still has no
  per-component attribution
- **Widen the coverage model** — created today. 30 bins is small: no bins for
  interrupt-enable combinations, none for the loopback mux itself, none for
  reset asserted mid-frame. Finding 9 is the warning attached to this item:
  check a new bin is reachable *before* adding it to a closure criterion
- **A less greedy steering policy** — created today. Steering here is
  first-unhit, the simplest policy there is; a real tool biases the
  constraint distribution rather than overriding it, and the difference shows
  up when constraints interact, which C1–C4 barely do
- **Mutants not yet attempted**: the overrun path, interrupt *enable*
  combinations, the loopback mux, the RX start-bit glitch filter
- **A property that actually needs a strengthening invariant** — studied and
  unexercised; blocked on the same bound
- **The SVA sequence layer** (`##`, `[*]`, `|->`, local variables) — runnable
  on neither tool here; worth one session establishing whether anything
  accessible closes the gap, since interviews assume fluency
- **A mutation script for `examples/phase4_uvm_milestone/`** — it has a report
  but no runnable script. Open since 2026-09-19
- **Code coverage measurement** (plan Section 5 targets 95%) — Icarus has no
  native support. Open since 2026-09-18
- Phase 6: lint, regression infra, coverage merge, CDC basics, interview-prep

**Automation health:** Device reachable, folder connected; neither repo had a
2026-09-24 entry, so a full session was run. `tools/setup_iverilog.sh` worked
first time; both 2026-09-17 gotchas still apply and both were avoided (source
it without a pipe; wrap the real binary in `timeout`, not the shell function).
**Two new operational findings:**

1. **`git config user.name/user.email` was missing in this clone** and the
   first commit failed with *"Author identity unknown"*. The identity had been
   set in a command that also ran a full `git clone` and was killed by the
   180-second tool timeout before reaching the `git config` lines. **Set the
   identity in its own call**, not appended to a long one.
2. **A full `git clone` of the graphene repo would not complete** over the
   session VM's proxy — four attempts, two with `early EOF` /
   `invalid index-pack output`, two silently stalled, one measurement at
   **238 B/s** while this repo cloned in 8.7 s. The working recipe is a
   partial + shallow + sparse clone that never requests the plot blobs
   (`git fetch --depth 1 --filter=blob:none`, `core.sparseCheckout` excluding
   `*.png`); 26 seconds instead of never. Recorded in full in that repo's
   log. The bridge also dropped twice mid-session; both times the in-flight
   command had **not** executed, and `git log` was the reliable check.

**Commits this run:** 4 (the bench with its runner and two recorded outputs;
the mutation harness with its report; the study note; progress.md). This
AUTOMATION_LOG.md entry makes 5.
