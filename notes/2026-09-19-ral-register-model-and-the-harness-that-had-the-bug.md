# RAL: what a register model buys, what it cannot express, and the mutation harness that had the bug it exists to catch

**Date:** 2026-09-19
**Phase:** 4 (UVM) — this closes the last remaining Phase 4 topic.
**Artifacts:** `examples/phase4_ral/` (testbench, Makefile, mutation script,
sim log, mutation report), `verification_plans/uart_controller_verification_plan.md` v2.

---

## 1. What a RAL actually is

Before today, every register access in this repo addressed registers by
number: `write(ADDR_CTRL, 0x0B)`. A register abstraction layer replaces the
number with an object — `regmodel.CTRL.write(status, 0x0B)` — and, much more
importantly, maintains a **mirror**: a model of what the hardware should
currently contain.

Four pieces:

| Piece | Job |
|---|---|
| `uvm_reg_block` | the map as a whole; owns the address map and the lock |
| `uvm_reg` / `uvm_reg_field` | one register; fields carry an **access policy** (RW, RO, WO, RC, W1C…) and a reset value |
| `uvm_reg_adapter` | translates a generic `uvm_reg_item` into the bus agent's own item, and back. Eighteen lines, and the only code that knows both worlds |
| `uvm_reg_predictor` | watches the bus **monitor** and updates the mirror from what was actually observed |

The payoff is not notation. It is two things:

1. **Generic sequences become available for free.** `uvm_reg_hw_reset_seq`
   reads every register and compares against its declared reset value.
   `uvm_reg_bit_bash_seq` walks *every bit* of every register, writing 1 and
   0 and reading back, and checks that RO bits do **not** stick. Nobody wrote
   either of them for this UART, and between them they killed three of the
   five mutants below.
2. **The mirror is a reference model of the register file** that nobody had
   to write by hand. The 2026-09-18 scoreboard hand-modelled exactly this,
   for exactly one register.

## 2. Explicit vs implicit prediction — and why this bench chose explicit

A RAL can update its mirror two ways.

- **Implicit (auto-predict).** The register object updates the mirror itself
  whenever `.write()`/`.read()` is called on it. It believes the write
  happened because the sequence asked for it.
- **Explicit.** The mirror is only updated by a predictor fed from the bus
  **monitor**. It believes the write happened only if the monitor saw it on
  the wire.

uvm-python, like UVM, defaults to `auto_predict = 0`, and this bench keeps it
off deliberately. This is the same rule the last two sessions' findings came
from — *never let the subsystem that did the work be the subsystem that grades
it*. Here it costs nothing, because the monitor already exists.

It also means the mirror tracks bus traffic that never went through the RAL.
CHECK 1 exercises exactly that: a raw `UartRegItem` is pushed at the
sequencer, nothing calls `CTRL.write()`, and the mirror still moves — to
**0x1B** for a write of 0xFB, because CTRL bits 7:5 are modelled RO. One
check proves prediction, the adapter's `bus2reg` path and the RO field
modelling at once.

## 3. The debug cycle worth recording

`uvm_reg.write()/read()/mirror()` take a `parent` that **must be a sequence**,
not a component: internally the map does `rw.parent.start_item(bus_req)`.
Passing the test component gives

    AttributeError: 'UartRalChecksTest' object has no attribute 'start_item'

which is what the first run of this bench did. The lesson generalises past
the error message: **the register layer sits on top of the sequence layer, it
does not bypass it.** A RAL access is still a sequence item arbitrated at a
sequencer, which is also why a RAL and a raw sequence can interleave safely
on the same bus.

## 4. What this UART breaks — the interesting part

Two of six registers cannot be honestly described by any `uvm_reg` access
policy, and pretending otherwise would have been the real mistake.

### 4.1 RX_DATA: a read with a side effect

Reading RX_DATA **pops the RX FIFO**. No access policy expresses "this read
mutates a queue elsewhere in the design". The model can describe the byte-wide
read port and nothing more. Tagged `NO_REG_TESTS`: a hw-reset sweep or a
bit-bash over it is silently consuming bytes another check is waiting for.

This is a general shape worth remembering: **RAL models the register
interface, not the design behind it.** Read-to-pop, write-to-trigger,
write-1-to-start — the register layer sees a register; the behaviour belongs
to the feature-level checks.

### 4.2 STATUS: two registers wearing one address

STATUS mixes four **volatile live** bits (tx_full, tx_empty, rx_full,
rx_avail) with three **sticky read-to-clear** error bits (frame_err,
parity_err, overrun_err). `RC` models the error bits correctly. The live bits
are marked volatile — and here is the trap:

> **UVM does not COMPARE volatile fields.** `uvm_reg_field::configure` sets
> the field's compare mode to `UVM_NO_CHECK` when `volatile` is set. So a
> `uvm_reg_hw_reset_seq` sweep over STATUS reads it, compares nothing, and
> reports success.

That is a check that looks like a check and is not one — the same shape as the
last two sessions' findings, this time built into the methodology rather than
into our code. The bench therefore checks STATUS's reset value (0x02:
tx_empty set, everything else clear) by hand, and **mutant M4 confirms it**:
swapping tx_full and tx_empty in the RTL is caught by the hand-written check
and by nothing else.

This is the **third independent confirmation** of the vplan's "live status"
defect — the RTL bring-up (2026-09-17), the UVM environment's read-to-clear
check (2026-09-18), and now the register model. `vplan v2` is written today
as a result.

## 5. The finding: the mutation harness had the bug it exists to catch

The first run of `run_mutation_tests.sh` reported **0 killed, 5 survived**.
Every one of the five logs contained the correct `FAIL`.

The script was trusting `make`'s exit status. With cocotb 1.9.2 + Icarus 10.3,
**`make` exits 0 even when cocotb prints `TESTS=1 PASS=0 FAIL=1`**. Verified
directly:

    $ make RTL_SRC=.../uart_controller_M3.v >/dev/null 2>&1; echo $?
    0

This is the **third appearance of one defect class in this repo**, and the
sequence is worth stating in one place:

| Date | Verdict came from | Checking was done by | Symptom |
|---|---|---|---|
| 2026-09-17 | the suite's own pass counter | checks that never executed | 55/55 against deliberately broken RTL |
| 2026-09-18 | cocotb's PASS line | the UVM report server | `PASS=1` with UVM_ERRORs in the log |
| 2026-09-19 | `make`'s exit code | cocotb's results line | every mutant reported as surviving |

Each time, **the subsystem reporting the verdict was not the subsystem doing
the checking, and nothing connected them.** Today it was the harness whose
entire purpose is to catch that, which is the strongest possible argument that
the rule generalises rather than being about one tool.

The fix parses cocotb's own results line and distinguishes a third outcome,
`NORESULT`, for a run that crashed or failed to compile — **a crash is not
evidence that a check works**, and counting it as a kill would be the same bug
one more time.

**Action for a future session:** `examples/phase4_uvm_milestone/` has a
mutation *report* but no script. Whoever automates it must not use `make`'s
exit code either.

## 6. Mutation results, and what they do not mean

Five defects, each targeting a different check, injected into **copies** of
the RTL (`rtl/uart_controller.v` is never modified). **5 killed, 0 survived.**

| Mutant | Defect | Killed by |
|---|---|---|
| M1 | CTRL reserved bit 5 reads back as 1 | `uvm_reg_bit_bash_seq` + `uvm_reg_hw_reset_seq` |
| M2 | BAUD_DIV resets to 0x01 | `uvm_reg_hw_reset_seq` |
| M3 | STATUS read-to-clear deleted | CHECK 6, the `RC` policy (second STATUS read) |
| M4 | STATUS tx_full/tx_empty swapped | CHECK 4, the hand-written reset check |
| M5 | BAUD_DIV writes dropped | CHECK 3 + bit-bash (16 errors) |

**Two honest qualifications.**

*M2 is not a clean single-target mutant.* Changing BAUD_DIV's reset value
halves the baud rate, so the hand-driven bad frame in CHECK 5 is also sent at
the wrong rate and frame_err never gets set. M2 is killed by the hw_reset
sequence as intended, but *also* by CHECK 5 for an unrelated reason. That is
collateral, not extra confidence: a mutant that trips two unrelated checks
tells you less about either than one that trips exactly its target.

*5/5 is a claim about five defects in the register interface*, not about the
DUT and not about the RAL. Untouched by any mutant here: the baud generator,
the TX/RX shift engines, the FIFO full/empty logic, the interrupt OR, the
loopback mux — and RX_DATA's pop-on-read, which is precisely the behaviour no
access policy can express and therefore the one thing the register model
structurally cannot check.

## 7. Toolchain notes (additive to 2026-09-06 and 2026-09-18)

- `tools/setup_iverilog.sh` works as fixed on 2026-09-18: **source it, do not
  pipe it**, and `iverilog`/`vvp` are now real scripts on PATH, so `timeout`
  wraps them normally.
- `cocotb-config` installs to `~/.local/bin`, which is **not on PATH** in this
  VM. `export PATH="$HOME/.local/bin:$PATH"` is required before `make`, or
  cocotb's Makefile include fails with an empty path.
- The RAL bench's Makefile takes an overridable `RTL_SRC`, so the mutation
  script points at a mutated copy without ever touching `rtl/`.
- uvm-python 0.4.0 ships the full `uvm.reg` package — `uvm_reg`,
  `uvm_reg_block`, `uvm_reg_field`, `uvm_reg_map`, `uvm_reg_adapter`,
  `uvm_reg_predictor`, and the built-in sequences under
  `uvm/reg/sequences/`. Nothing had to be written from scratch.

## 8. Sources

No web research was needed or attempted this session: the work was building
against this repo's own RTL and vplan plus the uvm-python source, which was
read directly at
`~/.local/lib/python3.10/site-packages/uvm/reg/` — in particular
`uvm_reg_field.py` (access policies and the volatile → `UVM_NO_CHECK`
behaviour), `uvm_reg_predictor.py`, and
`sequences/uvm_reg_hw_reset_seq.py` / `sequences/uvm_reg_bit_bash_seq.py`
(the `NO_REG_TESTS` / `NO_REG_BIT_BASH_TEST` resource names used in the model).
