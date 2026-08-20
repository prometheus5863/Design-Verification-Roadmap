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
