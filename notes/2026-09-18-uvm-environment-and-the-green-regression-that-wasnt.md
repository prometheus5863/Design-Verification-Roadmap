# The Phase 4 UVM environment, and a green regression that was hiding UVM_ERRORs

**Date:** 2026-09-18
**Code:** `examples/phase4_uvm_milestone/` (`uart_uvm_tb.py`, `Makefile`,
sim log, mutation report)
**DUT:** `rtl/uart_controller.v`, unmodified

---

## 1. What was built

The Phase 4 milestone environment, against the UART DUT brought up
(60/60 directed checks) on 2026-09-17. It closes three of the four items
`progress.md` still listed as unexercised.

### 1.1 Active vs passive agents — with a reason, not a flag

`UartSerialAgent` is one class instantiated twice:

* **active** on `rx` — sequencer + driver + monitor,
* **passive** on `tx` — monitor only, *no sequencer and no driver built
  at all*.

This is the textbook case rather than a contrived one: `tx` is a DUT
**output**. An agent there physically cannot be active, and building a
driver for it would be a contention bug waiting to happen. `connect_phase`
on the passive branch carries a runtime assertion that neither child was
built, because `progress.md` has carried "the active/passive distinction
itself is not yet exercised" since 2026-09-06 and a flag that is merely
*set* is not an exercise of it.

### 1.2 Virtual sequencer and genuinely concurrent sequences

`UartVirtualSequencer` holds handles to the register sequencer and the
serial sequencer. `UartFullDuplexVSeq` reaches them through
`get_sequencer()` (uvm-python names the field `m_sequencer`; there is no
`self.sequencer` property, which cost one debug cycle) and starts the
register-side TX sequence and the serial-side RX sequence with
`cocotb.start_soon`, awaiting both.

The concurrency is the point. The DUT transmits and receives *at the same
time*; two sequences run back to back would never produce that, and
full-duplex is where a shared-resource bug in the DUT would actually
live.

### 1.3 Reference-model scoreboard on three analysis imps

`uvm_analysis_imp_decl` for `_reg`, `_rx` and `_tx`. Three prediction
paths: TX_DATA writes predict frames on `tx`; frames seen on `rx` predict
RX_DATA reads; corrupted frames predict STATUS error bits. The scoreboard
is fed only from monitors, never from drivers — a driver that silently did
nothing would otherwise still "pass".

Baseline: **69 checks, 0 errors, 12 rx + 15 tx frames decoded, 100.0%
functional bin coverage** across five coverpoints and one cross, under
three frame formats (none/1 stop, even/1, odd/2). Coverage below target
raises a UVM_ERROR rather than printing a number nobody reads.

Still not done: **RAL**. The register map is driven through an explicit
bus agent, which is exactly what a RAL model would sit on top of.

---

## 2. The finding: a green regression that contained UVM_ERRORs

The environment passed on the first real run. Per this repo's practice
since 2026-09-17, it was then mutation tested — a defect injected into a
*copy* of the RTL, with the suite required to fail.

**The first two mutants "survived".** They had not. The scoreboard had
caught both and printed the correct diagnostics:

```
UVM_ERROR ... tx frame 0x00 parity bit correct (got 1, expected 0)
...
** TESTS=1 PASS=1 FAIL=0 SKIP=0 **
```

The log contained the evidence and the summary line contradicted it.

### Why

cocotb's pass/fail verdict comes from whether the test coroutine raised
an exception. It has no knowledge of the UVM report server's severity
counts, and **uvm-python does not bridge the two**. `uvm_report_error`
increments a counter, prints, and returns. Nothing in the default flow
turns that counter into a failing test.

This is the same class of defect as the 2026-09-17 finding (a testbench
that passed 55/55 against deliberately broken RTL), reached from the
opposite direction:

| | 2026-09-17 | 2026-09-18 |
|---|---|---|
| checks written | yes | yes |
| checks executed | **no** (polling loop never advanced) | yes |
| checks failed correctly | — | **yes** |
| verdict reported | PASS | PASS |

The 2026-09-18 version is arguably worse. A testbench that runs no checks
at least looks suspicious when someone reads the log. One that runs them,
fails them, prints them, and then announces PASS actively teaches the
reader to trust a summary line that is wrong.

### Fix

`UartMilestoneTest.report_phase` now reads the report server's
`UVM_ERROR` / `UVM_FATAL` counts and asserts they are zero. `report_phase`
executes bottom-up, so every child's errors — scoreboard, coverage
target, drain check — are already counted by the time it runs.

**The general lesson, worth carrying into Phases 5 and 6: whenever the
subsystem that decides pass/fail is not the subsystem doing the checking,
the two have to be wired together explicitly, and the wire has to be
tested.** That applies to a formal tool's exit code, a regression
runner's parse of a log, and a coverage merge that silently drops a
database, not just to this one combination.

---

## 3. The second hole: checking that a bit sets is not checking a sticky bit

With the verdict fixed, four mutants died and one lived: **M3, the
mutant with STATUS read-to-clear deleted entirely.**

The drain sequence read STATUS once per run, and every run injects fresh
errors before its read. So an error bit that *never* clears is
indistinguishable from one that is correctly re-set by the next run's
injected error. The regression was checking half of a read-to-clear
register.

Fix: read STATUS **twice**. The first read checks the bits were SET; only
the second checks that the first read CLEARED them. M3 then dies on the
second read (expected 0, got 1).

This is the pending vplan v2 issue stated as a check rather than as
prose. The verification plan calls STATUS "live"; the RTL implements the
error bits sticky and read-to-clear (documented deviation, 2026-09-17).
**A sticky bit needs two checks, and a plan that calls it "live" produces
a testbench that writes only one of them.** The v2 revision is now
motivated from two independent directions — the RTL bring-up and the UVM
environment — which is worth more than either on its own.

Final mutation result: **5 injected, 5 killed, 0 survivors.** Not covered
by any mutant: the baud generator, the overrun path, the interrupt logic,
the FIFO full/empty flags and the loopback mux. Those are the obvious
next mutants and the obvious next coverpoints; 5/5 is a claim about these
five defects, not about the DUT.

A smaller note in the same spirit: mutant M2 (RX shifted MSB-first) is
**not** distinguished by the byte `0x5A`, which is bit-symmetric. It was
killed by `0x01` → `0x80`. A stimulus set that happened to use only
palindromic bytes would have let a bit-reversal bug through, which is a
concrete argument for the value-diversity coverpoint rather than an
abstract one.

---

## 4. Toolchain: two fixes to `tools/setup_iverilog.sh`

Every `make` in the new directory first failed with

```
Makefile.icarus:53: *** Unable to locate command >iverilog<
```

in a shell where `iverilog -V` plainly worked.

1. **Shell functions are invisible to child processes** that do their own
   command lookup. The script defined `iverilog`/`vvp` only as functions.
   It now also installs real two-line wrapper scripts (carrying the
   `-B`/`-M` flags) in `$IVERILOG_INSTALL_DIR/bin` and prepends that to
   PATH. This also supersedes the 2026-09-17 workaround of invoking the
   real binary by absolute path to wrap it in `timeout`: `timeout 150 vvp
   sim` now works, because `vvp` is a file.

2. **`export -f` actively poisoned cocotb's detection.** cocotb's
   `Makefile.inc` sets `SHELL := bash`, and `Makefile.icarus` does

   ```make
   CMD := $(shell :; command -v iverilog)
   ICARUS_BIN_DIR := $(shell dirname $(CMD))
   ```

   In a bash that has imported an exported *function* of that name,
   `command -v iverilog` prints the bare word `iverilog`, so `dirname`
   yields `.`, cocotb looks for `./iverilog`, and reports the misleading
   error above. The functions are no longer exported; children resolve
   the PATH scripts and get a correct `ICARUS_BIN_DIR`.

Both examples (`phase4_uvm_milestone` and the older `phase4_uvm_python`)
now run with `make` after nothing but `source tools/setup_iverilog.sh`.
Sourcing it, not piping it, still matters — piping runs it in a subshell
and both the functions and the PATH change vanish.
