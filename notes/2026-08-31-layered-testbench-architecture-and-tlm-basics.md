# Study notes: layered testbench architecture + TLM basics (Phase 3)

*Date: 2026-08-31. Phase 3 ("Verification Methodology Fundamentals")
begins here -- Phase 2 (SystemVerilog for Verification) completed
2026-08-29. Covers the first two `progress.md` Phase 3 items together
("Layered testbench architecture concepts" and "TLM basics") since they
are directly coupled: TLM is the mechanism the layers communicate
through, and neither is fully separable from the other in explaining
*why* the architecture looks the way it does. WebSearch/WebFetch were
available and used to confirm/ground the material against current
online references, alongside stable IEEE 1800/UVM methodology content.*

## 1. Why a layered testbench at all?

A **directed testbench** -- one `initial` block that generates stimulus,
drives DUT pins, and checks results all in one linear sequence -- is
exactly what this repo's Phase 1 milestone
(`examples/phase1_milestone/sync_fifo_directed_tb.v`) and Phase 2's
first example (`examples/phase2/alu_if_tb.sv`) already are. It works
fine for a small DUT and a handful of directed test cases, and this
repo used it deliberately at that stage rather than jumping straight to
a layered structure it wasn't yet ready to justify.

Two things break down as a design and its verification effort grow:

1. **Reuse.** A directed testbench's stimulus-generation code, pin-level
   driving code, and checking code are all interleaved in one block. To
   write a new test scenario against the *same DUT*, or to reuse the
   *same driving/checking logic* against a related DUT (a new revision,
   a similar peripheral), there is no natural seam to reuse just one
   piece -- the whole block gets copy-pasted and hand-edited, which is
   both effort-heavy and a correctness risk (the copies drift).
2. **Separation of stimulus from checking.** A directed test hard-codes
   both "what to send" and "what to expect" together, so it can only
   ever check the exact scenarios someone thought to write by hand.
   Later, moving to randomized (Phase 2, already covered: this repo's
   manual `dist`/`randc`-style workarounds) or coverage-driven
   stimulus (Phase 2, functional coverage) requires the checking logic
   to be *independent* of any particular stimulus sequence -- it has to
   work by comparing DUT behavior against a reference model for
   whatever transaction actually showed up, not by knowing in advance
   what was sent.

The layered architecture is the standard industry answer to both
problems (Bergeron, *Writing Testbenches using SystemVerilog*; this
repo's README Phase 3 resource list): split the directed testbench's
one undifferentiated block into named objects, each with one job, that
communicate over defined channels rather than sharing code directly.

## 2. The layers

Standard decomposition (consistent across VMM/OVM/UVM lineage and the
2013-era ChipVerify/Maven Silicon tutorials fetched this session --
Sources 1-2 below):

- **Transaction** -- a data object (a class in SV) representing one
  unit of stimulus or one unit of observed DUT activity at the
  *protocol* level (e.g. "an ADD of 0x3 and 0x5"), not the pin level
  (e.g. not "drive `a`=00000011, `b`=00000101, `op`=000 for one clock").
  This repo already has this piece: `alu_transaction` in
  `examples/phase2/alu_oop_tb_components.sv` (2026-08-25).
- **Sequencer / generator** -- produces a stream of transactions
  (directed, randomized, or coverage-driven) and hands them off, one at
  a time, to a driver. (UVM formalizes this as a `sequencer` +
  `sequence` pair; this repo's simpler "generator" terminology, already
  used in the Phase 2 examples, is the same role without UVM's
  additional sequence-arbitration machinery.)
- **Driver** -- receives a transaction and translates it into pin-level
  activity on the DUT interface, cycle by cycle, per the DUT's actual
  protocol timing. This is where an abstract transaction becomes real
  signal wiggles.
- **Monitor** -- the driver's mirror image: watches DUT interface pins
  passively (never drives anything) and reconstructs transactions from
  observed pin activity, for both input-side and output-side checking.
  A monitor is what lets the same interface be checked without
  interfering with how it's being driven.
- **Agent** -- a container bundling one generator + one driver + one
  monitor, all specific to a single DUT interface/protocol. The point
  of grouping them is reuse: an agent for a given protocol (e.g. "an
  APB agent") can be dropped into any environment that has an APB
  interface, unmodified. An agent can be **active** (has a
  driver, generates stimulus) or **passive** (monitor only, e.g. for
  observing a bus this environment doesn't drive).
- **Scoreboard** -- an independent checker, decoupled from stimulus
  generation entirely, that receives observed transactions (from one or
  more monitors) and compares them against a reference model's expected
  values. This repo's `alu_scoreboard` class (2026-08-25) is this role,
  though on this build it does its own re-derivation of expected
  results inline rather than a fully separate reference-model object --
  a simplification, not a different architecture.
- **Environment** -- the container one level up from an agent: holds
  one or more agents (a real DUT often has more than one interface --
  e.g. a bus-side agent and an interrupt-side agent) plus the
  scoreboard(s) that check across them, and wires the monitors'
  observed-transaction outputs to the scoreboard's inputs.
- **Test** -- the top-level entry point: builds one specific environment
  configuration and kicks off one specific sequence of stimulus (e.g.
  "the reset test", "the corner-case-op test"). Different tests reuse
  the *same* environment/agent/scoreboard code and differ only in
  configuration and which sequence(s) they run -- this is the payoff of
  everything below it being decoupled.

## 3. TLM basics: why transactions, not pins, between layers

Given the layers above, the next question is *how* a generator hands a
transaction to a driver, or a monitor hands an observed transaction to
a scoreboard, without those two objects needing to know about each
other's internals. This is exactly what Transaction-Level Modeling
(TLM) is for (Source 3, chipverify.com, fetched this session):

- A **port** is declared by the object that wants to *send* (a
  generator's port to its driver; a monitor's port to a scoreboard).
- An **export** is declared by the object that *receives*, exposing an
  implementation of the actual handling logic (an **imp** in UVM's
  three-part port/export/imp terminology).
- Connecting a port to an export at environment-build time is the only
  place the two objects' existence is coupled together -- neither
  object's *internal code* references the other by name, so either can
  be swapped for a different implementation (a different driver variant,
  a different scoreboard) without touching the other.
- **Analysis ports** are the specific TLM pattern used for monitor ->
  scoreboard (and monitor -> coverage collector) hand-off: a monitor
  calls `write()` on its analysis port once per observed transaction,
  and *every* connected export receives it (broadcast, zero or more
  subscribers) -- the monitor does not know or care how many scoreboards
  or coverage collectors are listening, or whether there are any at
  all. This is precisely the property that lets a coverage collector be
  bolted onto an existing environment later without modifying the
  monitor that already exists.

The classic TLM channel implementing point-to-point (not broadcast)
transaction hand-off is a `mailbox` -- exactly the mechanism this
repo's own Phase 2 example (`alu_oop_tb_components.sv`, note 5)
already tried to use for generator -> driver hand-off and found
**not implemented at all** on the pinned Icarus Verilog 10.3 build.
That finding, from a different angle, is really a TLM-channel finding:
this build lacks the language-level channel type standard SV/UVM code
uses to connect layers, which is exactly why that example fell back to
a single reused transaction handle passed directly between plain tasks
instead of a real generator/driver split communicating over a channel
(see Section 4).

## 4. What this repo's toolchain can and cannot actually build

Section 2 describes a full layered architecture as industry (and UVM)
implement it. This repo's pinned Icarus Verilog 10.3 build
(`tools/setup_iverilog.sh`) cannot fully realize it, and it is worth
stating plainly *why*, synthesizing the individual gaps already found
and logged across Phase 2 (`notes/2026-08-25-oop-testbench-
components.md` and this session's re-reading of
`examples/phase2/alu_oop_tb_components.sv`'s header, notes 5-9) rather
than re-discovering them piecemeal in Phase 4:

- No `mailbox` (or `semaphore`) -- rules out the standard point-to-point
  TLM channel type described in Section 3.
- A class cannot hold a `virtual <interface>` member -- rules out the
  one mechanism a driver/monitor class uses to reach DUT pins from
  inside a class at all. This is the most consequential gap: it means
  a driver and monitor literally **cannot be written as class objects**
  that drive/observe a DUT interface on this build, independent of the
  mailbox gap above.
- Class handles cannot be passed as `input`/`ref` task arguments, only
  `output`, and cannot be stored in queues or (variable-indexed) arrays
  -- rules out passing transaction objects freely between arbitrary
  layer objects, and rules out an agent/environment holding a
  dynamically-sized collection of sub-components or transactions the
  way UVM's `uvm_component`/`uvm_object` machinery does throughout.

Net conclusion (consistent with, and now given a unified explanation
for, the note already recorded 2026-08-25): this Icarus 10.3 build can
express the **transaction/generator/scoreboard** roles as real class
objects with persistent state and can demonstrate the *conceptual*
generator -> driver -> DUT -> monitor -> scoreboard data flow, but the
**driver and monitor roles cannot be realized as class objects** here --
they remain plain procedural code directly in a module's `initial`
block, immediately adjacent to where each transaction is
generated/consumed, as `alu_oop_tb_components.sv` and
`alu_combined_tb.sv` (Phase 2 milestone) both already do in practice.
A full layered testbench, and certainly a real UVM environment (Phase
4), is not achievable on this specific toolchain -- Phase 4 will need a
different simulator (Verilator has broader class support but its own
gaps; a free/student-tier commercial simulator such as Questa or VCS is
the realistic path for an actual UVM testbench), a conclusion the
2026-08-25 notes already reached and this session's re-reading confirms
rather than overturns.

No new illustrative code file is added this session as a result: the
conceptual layering is already about as fully demonstrated as this
toolchain allows in the existing Phase 2 examples (transaction +
generator + scoreboard as real classes; driver/monitor as adjacent
procedural code, explicitly because of, not despite, the tooling
limits above), and writing a new example today would either duplicate
`alu_oop_tb_components.sv`/`alu_combined_tb.sv` or re-hit the same
already-documented gaps. Phase 3's own milestone (a written
verification plan) and Phase 4's UVM work are the more useful places to
apply today's conceptual grounding once a suitable toolchain question
is resolved for Phase 4.

## 5. What this sets up: verification planning (next `progress.md` item)

The remaining two Phase 3 topics -- the verification plan (features ->
checks -> coverage -> tests) and the directed-vs-constrained-random-
vs-coverage-driven trade-off discussion -- both presuppose the
vocabulary established here (agent, scoreboard, environment, transaction)
and are left for a following session's `progress.md` item rather than
compressed into today's entry, consistent with this repo's practice of
one coherent topic (here, two tightly-coupled ones) per session rather
than rushing through a whole phase's remaining items at once.

## References

1. "SystemVerilog Testbench/Verification Environment Architecture."
   Maven Silicon Blog. https://www.maven-silicon.com/blog/systemverilog-testbench-verification-environment-architecture/
2. "SystemVerilog TestBench." Verification Guide.
   https://verificationguide.com/systemverilog/systemverilog-testbench/
3. "UVM TLM Analysis Port." ChipVerify.
   https://chipverify.com/uvm/uvm-tlm-analysis-port
4. Bergeron, J. *Writing Testbenches using SystemVerilog*, Springer
   (canonical text on testbench architecture and methodology reasoning;
   README Phase 3 resource list).
5. Accellera. *Universal Verification Methodology (UVM) 1.2 User's
   Guide*. https://accellera.org/images/downloads/standards/uvm/uvm_users_guide_1.2.pdf
6. `examples/phase2/alu_oop_tb_components.sv`,
   `notes/2026-08-25-oop-testbench-components.md` (this repo) --
   source of the mailbox/virtual-interface-in-class/class-handle-
   argument tooling gaps synthesized in Section 4.
