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
