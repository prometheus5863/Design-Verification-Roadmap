#!/usr/bin/env python3
"""
build_variants.py -- generate every (property-dropped, mutant) RTL variant
for the per-property mutation-coverage measurement.

WHY THIS FILE EXISTS.  2026-09-22 applied a deletion experiment to exactly
one property (R4) because that was the one it suspected, and found it
subsumed: no mutant could distinguish the suite with R4 from the suite
without it.  The log made "per-property mutation coverage for the whole
suite" the top open item, on the grounds that the question had just been
shown to have a non-trivial answer and had never been asked of the
2026-09-20 FIFO invariants (P1-P4) or the 2026-09-21 CSR properties (C1-C9).

THE MEASUREMENT.  For a property p and a mutant m:

    baseline(m)   = verdict of the FULL suite on RTL+m       (expect FAIL)
    drop(p)       = verdict of the suite without p on clean RTL (expect PASS)
    drop(p, m)    = verdict of the suite without p on RTL+m

  * drop(p, m) == PASS while baseline(m) == FAIL  =>  p is the ONLY property
    that detects m.  p is LOAD-BEARING for m.
  * drop(p, m) == FAIL                            =>  m is still caught
    without p.  p earns nothing from m.
  * drop(p) != PASS                               =>  the deletion broke the
    build or the remaining suite.  INCONCLUSIVE, never scored as a result.

A property with no load-bearing mutant is SUBSUMED with respect to this
mutant set.  That is a statement about the mutant set, not a proof of
redundancy, and the report says so.

ORDER MATTERS.  The mutant is applied FIRST, to the pristine file, and the
property block is deleted afterwards -- the reset mutants of 2026-09-22 are
line-numbered seds, and deleting a block first would shift every line under
it.  Mutants here are exact string replacements rather than seds, and each
one asserts that it changed the file, so a mutant that silently matches
nothing cannot be scored as "detected" by accident.
"""
import os
import sys

SUITES = {
    "fifo": dict(
        sby="examples/phase5_formal_uart/uart_fifo_bmc.sby",
        props=["P1", "P2", "P3", "P4"],
        # Every property VISIBLE to this job's compile, which is not the same
        # as the properties the suite was written with -- see `active`.
        active=["P1", "P2", "P3", "P4"],
        region="`ifdef FORMAL\n",
        end_banner="    // ---- C1: cover, to prove the properties are not vacuous",
        mutants={
            "M1": ("TX push no longer guarded by ~tx_full (overflow)",
                   "wire tx_push = wr_en & (paddr == ADDR_TX_DATA) & ~tx_full;",
                   "wire tx_push = wr_en & (paddr == ADDR_TX_DATA);"),
            "M2": ("RX pop no longer guarded by rx_avail (underflow)",
                   "wire rx_pop  = rd_en & (paddr == ADDR_RX_DATA) & rx_avail;",
                   "wire rx_pop  = rd_en & (paddr == ADDR_RX_DATA);"),
            "M3": ("TX count increments by 2 per push",
                   "2'b10: tx_cnt <= tx_cnt + 4'd1;",
                   "2'b10: tx_cnt <= tx_cnt + 4'd2;"),
            "M4": ("TX write pointer advances by 2",
                   "if (tx_push) begin tx_fifo[tx_wptr] <= pwdata; "
                   "tx_wptr <= tx_wptr + 3'd1; end",
                   "if (tx_push) begin tx_fifo[tx_wptr] <= pwdata; "
                   "tx_wptr <= tx_wptr + 3'd2; end"),
            "M5": ("simultaneous push+pop wrongly decrements the count",
                   "2'b01: tx_cnt <= tx_cnt - 4'd1;",
                   "2'b01: tx_cnt <= tx_cnt - 4'd1; 2'b11: tx_cnt <= tx_cnt - 4'd1;"),
        },
        # GAP-CLOSING mutants added 2026-09-23, kept in their own dict so the
        # 2026-09-20 matrix above is reproducible unchanged.
        gap_mutants={
            "M6": ("tx_full uses the empty constant, so full and empty "
                   "coincide (P3)",
                   "    wire tx_full  = (tx_cnt == 4'd8);",
                   "    wire tx_full  = (tx_cnt == 4'd0);"),
        },
    ),
    "csr": dict(
        sby="examples/phase5_csr_formal/uart_csr_bmc.sby",
        props=["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"],
        # The CSR job compiles -DFORMAL -DFORMAL_CSR, so the 2026-09-20 FIFO
        # invariants are SILENTLY PRESENT in it. Any "CSR property" found
        # subsumed may be subsumed by another day's suite.
        active=["P1", "P2", "P3", "P4",
                "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"],
        region="`ifdef FORMAL_CSR\n",
        end_banner="    // ---- C10: covers -- the CSR suite must not be vacuous",
        mutants={
            "N1": ("write decode aliases CTRL onto the STATUS address",
                   "                ADDR_CTRL:     ctrl     <= pwdata[4:0];",
                   "                ADDR_CTRL:     ctrl     <= pwdata[4:0];\n"
                   "                ADDR_STATUS:   ctrl     <= pwdata[4:0];"),
            "N2": ("CTRL reserved bits read as 1",
                   "            ADDR_CTRL:     prdata = {3'b000, ctrl};",
                   "            ADDR_CTRL:     prdata = {3'b111, ctrl};"),
            "N3": ("unmapped and write-only addresses read 0xFF",
                   "            default:       prdata = 8'h00;",
                   "            default:       prdata = 8'hFF;"),
            "N4": ("STATUS tx_full/tx_empty bits swapped",
                   "    wire [7:0] status_val = {1'b0, overrun_err, parity_err, frame_err,",
                   "    wire [7:0] status_val = {1'b0, overrun_err, parity_err, frame_err,\n"
                   "                             rx_avail, rx_full, tx_full, tx_empty}; // MUTANT\n"
                   "    wire [7:0] status_unused = {1'b0, overrun_err, parity_err, frame_err,"),
            "N6": ("RX_DATA read pops an empty FIFO",
                   "    wire rx_pop  = rd_en & (paddr == ADDR_RX_DATA) & rx_avail;",
                   "    wire rx_pop  = rd_en & (paddr == ADDR_RX_DATA);"),
            "N7": ("TX-empty interrupt ignores its mask bit",
                   "    assign irq = (tx_empty & int_en[0])",
                   "    assign irq = (tx_empty)"),
        },
        # GAP-CLOSING mutants added 2026-09-23. Phase 2 found C1 and C6
        # UNEXERCISED: nothing in N1-N7 is visible to them. C1's own comment
        # says "a width mutation is exactly what this catches" and no width
        # mutation had ever been injected; C6 describes the read-to-clear
        # path and no mutant touched it. N10 is a control for N9.
        gap_mutants={
            "N8": ("INT_EN write drops its top bit (width defect -- C1)",
                   "                ADDR_INT_EN:   int_en   <= pwdata[2:0];",
                   "                ADDR_INT_EN:   int_en   <= pwdata[1:0];"),
            "N9": ("a STATUS read no longer clears frame_err (C6)",
                   "                frame_err <= 1'b0; parity_err <= 1'b0; "
                   "overrun_err <= 1'b0;",
                   "                parity_err <= 1'b0; overrun_err <= 1'b0;"),
            "N10": ("CONTROL for N9: a STATUS read SETS frame_err. C6 must "
                    "detect this, or C6 is broken rather than bounded.",
                    "                frame_err <= 1'b0; parity_err <= 1'b0; "
                    "overrun_err <= 1'b0;",
                    "                frame_err <= 1'b1; parity_err <= 1'b0; "
                    "overrun_err <= 1'b0;"),
        },
    ),
    "reset": dict(
        sby="examples/phase5_csr_formal/uart_reset_bmc.sby",
        props=["R1", "R2", "R3", "R4"],
        # -DFORMAL -DFORMAL_CSR_RESET: the FIFO invariants are here too.
        active=["P1", "P2", "P3", "P4", "R1", "R2", "R3", "R4"],
        region="`ifdef FORMAL_CSR_RESET",
        end_banner="    // ---- COVERS: R1-R4 are not vacuous",
        gap_mutants={},
        mutants={
            "K1": ("CTRL not cleared by reset",
                   "ctrl <= 5'd0;", "ctrl <= ctrl;"),
            "K2": ("TX line idles LOW out of reset",
                   "tx_line <= 1'b1;", "tx_line <= 1'b0;"),
            "K3": ("a concurrent bus write beats reset",
                   "        if (!rst_n) begin\n            ctrl",
                   "        if (!rst_n && !wr_en) begin\n            ctrl"),
            "K4": ("TX FIFO count resets to 1, so STATUS.tx_empty is wrong",
                   "tx_cnt <= 4'd0;", "tx_cnt <= 4'd1;"),
            "K5": ("frame_err sticky bit resets SET",
                   "frame_err <= 1'b0;", "frame_err <= 1'b1;"),
            "K6": ("irq ignores its enable mask",
                   "    assign irq = (tx_empty & int_en[0])",
                   "    assign irq = (tx_empty)"),
        },
    ),
}

BANNER = "    // ---- {p}"


PROP_REGION = {"P": "`ifdef FORMAL\n",
               "C": "`ifdef FORMAL_CSR\n",
               "R": "`ifdef FORMAL_CSR_RESET"}
PROP_END = {"P": "    // ---- C1: cover, to prove the properties are not vacuous",
            "C": "    // ---- C10: covers -- the CSR suite must not be vacuous",
            "R": "    // ---- COVERS: R1-R4 are not vacuous"}
PROP_ORDER = {"P": ["P1", "P2", "P3", "P4"],
              "C": ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"],
              "R": ["R1", "R2", "R3", "R4"]}


def span(src, prop):
    """
    (start, end) of one property block, searched INSIDE its own `ifdef region.

    The region anchor is not decoration. The FIFO suite's cover block is
    also called "C1" (`// ---- C1: cover, to prove the properties are not
    vacuous`, inside `ifdef FORMAL`), so a bare search for "    // ---- C1"
    finds the FIFO block and deletes from there to the CSR C2 banner -- across
    two `endif`s. The first run of this harness did exactly that and the job
    came back `ERROR: Found \`endif outside of macro conditional branch`.
    Guard G3 turned it into INCONCLUSIVE instead of a wrong answer, which is
    the whole reason G3 exists.
    """
    fam = prop[0]
    base = src.index(PROP_REGION[fam])
    start = src.find("    // ---- " + prop, base)
    if start < 0:
        raise SystemExit(f"banner for {prop} not found in its region")
    order = PROP_ORDER[fam]
    end = -1
    for q in order[order.index(prop) + 1:]:
        end = src.find("    // ---- " + q, base)
        if end >= 0:
            break
    if end < 0:
        end = src.find(PROP_END[fam], base)
    if end < 0:
        raise SystemExit(f"end banner after {prop} not found")
    return start, end


def remove_props(src, props):
    """Delete a set of property blocks, back to front so offsets stay valid."""
    spans = sorted((span(src, p) for p in props), reverse=True)
    for a, b in spans:
        src = src[:a] + src[b:]
    return src


def drop_property(src, prop, _props=None, _end=None):
    return remove_props(src, [prop])


def apply_mutant(src, spec):
    desc, old, new = spec
    if old not in src:
        raise SystemExit(f"mutant text not found in RTL: {old[:60]!r}")
    out = src.replace(old, new, 1)
    if out == src:
        raise SystemExit(f"mutant changed nothing: {desc}")
    return out


# Phase 3: which property each gap-closing mutant was written for.
GAP_PLAN = [("csr", "C1", "N8"), ("csr", "C6", "N9"), ("fifo", "P3", "M6")]
# Gap mutants that are CONTROLS rather than targeted tests: run against the
# full suite only.
GAP_CONTROLS = [("csr", "N10")]


def build_gap(root, work, rtl):
    jobs = []
    for suite, prop, m in GAP_PLAN:
        cfg = SUITES[suite]
        sby = open(os.path.join(root, cfg["sby"])).read().replace(
            "../../rtl/uart_controller.v", "uart_controller.v")
        mut = apply_mutant(rtl, cfg["gap_mutants"][m])
        others = [q for q in cfg["active"] if q != prop]
        for name, text in ((f"base__{m}", mut),
                           (f"drop{prop}__{m}", remove_props(mut, [prop])),
                           (f"only{prop}__{m}", remove_props(mut, others))):
            d = os.path.join(work, suite, name)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "uart_controller.v"), "w").write(text)
            open(os.path.join(d, "m.sby"), "w").write(sby)
            jobs.append(d)
    for suite, m in GAP_CONTROLS:
        cfg = SUITES[suite]
        sby = open(os.path.join(root, cfg["sby"])).read().replace(
            "../../rtl/uart_controller.v", "uart_controller.v")
        d = os.path.join(work, suite, f"base__{m}")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "uart_controller.v"), "w").write(
            apply_mutant(rtl, cfg["gap_mutants"][m]))
        open(os.path.join(d, "m.sby"), "w").write(sby)
        jobs.append(d)
    return jobs


def main():
    root, work = sys.argv[1], sys.argv[2]
    if "--gap" in sys.argv[3:]:
        rtl = open(os.path.join(root, "rtl", "uart_controller.v")).read()
        jobs = build_gap(root, work, rtl)
        with open(os.path.join(work, "jobs.txt"), "w") as f:
            f.write("\n".join(jobs) + "\n")
        print(f"{len(jobs)} gap variants built under {work}")
        return
    targets = []
    for a in sys.argv[3:]:            # phase 2: "suite/PROP" solo variants
        suite, prop = a.split("/")
        targets.append((suite, prop))
    rtl = open(os.path.join(root, "rtl", "uart_controller.v")).read()
    jobs = []
    for suite, cfg in SUITES.items():
        sby = open(os.path.join(root, cfg["sby"])).read().replace(
            "../../rtl/uart_controller.v", "uart_controller.v")
        variants = {}
        if not targets:
            variants["base__clean"] = rtl
            for m, spec in cfg["mutants"].items():
                variants[f"base__{m}"] = apply_mutant(rtl, spec)
            for p in cfg["props"]:
                variants[f"drop{p}__clean"] = remove_props(rtl, [p])
                for m, spec in cfg["mutants"].items():
                    variants[f"drop{p}__{m}"] = remove_props(
                        apply_mutant(rtl, spec), [p])
        else:
            for s2, p in targets:
                if s2 != suite:
                    continue
                others = [q for q in cfg["active"] if q != p]
                variants[f"only{p}__clean"] = remove_props(rtl, others)
                variants[f"drop{p}__clean"] = remove_props(rtl, [p])
                for m, spec in cfg["mutants"].items():
                    variants[f"only{p}__{m}"] = remove_props(
                        apply_mutant(rtl, spec), others)
                    variants[f"drop{p}__{m}"] = remove_props(
                        apply_mutant(rtl, spec), [p])
        for name, text in variants.items():
            d = os.path.join(work, suite, name)
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "uart_controller.v"), "w").write(text)
            open(os.path.join(d, "m.sby"), "w").write(sby)
            jobs.append(d)
    with open(os.path.join(work, "jobs.txt"), "w") as f:
        f.write("\n".join(jobs) + "\n")
    print(f"{len(jobs)} variants built under {work}")


if __name__ == "__main__":
    main()
