//------------------------------------------------------------------------
// alu_if_and_dut.sv
//
// Phase 2 example: SystemVerilog data types + interfaces/modports.
//
// Demonstrates, in one small self-contained design:
//   - a packed enum type for the ALU opcode (readable in waveforms,
//     unlike a bare 3-bit code, and gives the compiler/simulator a
//     restricted value set to catch typos)
//   - a packed struct bundling the ALU result's status flags
//     (zero/carry/overflow) as a single typed object instead of three
//     loose wires
//   - an `interface` bundling the DUT<->testbench connection, with two
//     `modport`s (`dut` and `tb`) giving each side a *direction-checked*
//     view of the same signals -- the idiomatic reason to use an
//     interface at all
//
// TOOLING NOTES (found this session, 2026-08-24, all against the
// Icarus Verilog 10.3 build this repo's tools/setup_iverilog.sh
// installs -- see that script and the 2026-08-23 AUTOMATION_LOG.md
// entry for the two gaps found that day; this session found several
// more, all confirmed with minimal standalone repros before working
// around them here, so these are real toolchain limits, not bugs in
// this file's logic):
//
//   1. Interfaces cannot be used as module ports at all, in any syntax
//      form (`alu_if.dut vif`, `alu_if vif`, ANSI or non-ANSI style;
//      tried all four with `-g2012` and `-g2005-sv`) -- every form fails
//      with the same "Errors in port declarations" syntax error, even
//      for a two-line minimal interface with no modports. The interface
//      *declaration* below (with modports) compiles cleanly on its own;
//      it just cannot be used to type a module port on this build.
//   2. `always_comb` does not compile at all on this build, in any form
//      (single-statement or `begin/end` block), even completely
//      standalone with no ports, structs, or enums involved. Confirmed
//      with a 3-line minimal repro. `always_ff` likewise does not
//      compile (minimal repro: a 4-line register with async reset).
//      Plain Verilog-2001-style `always @*` and
//      `always @(posedge clk or negedge rst_n)` -- the style already
//      used throughout this repo's Phase 1 examples -- work fine and are
//      used below instead.
//   3. `unique case` / `priority case` do not compile; plain `case` (as
//      already used in Phase 1) works and is used below.
//   4. SystemVerilog assignment-pattern syntax (`'{default: 1'b0}`,
//      `'0` fill) does not compile for a packed-struct target; per-field
//      assignment (`flags.zero <= 1'b0;` etc.) works and is used below.
//
// Given (1)-(4), this Icarus 10.3 build's practical SystemVerilog support
// is closer to "Verilog-2001 plus typedef enum/struct and interface/
// always @* declarations" than to full IEEE 1800-2017 support -- useful
// to know heading into the rest of Phase 2 (classes, randomization,
// coverage are all *more* advanced SV than any of the above, so those
// examples should be spot-checked early too rather than assumed to
// compile, exactly as the 2026-08-23 log entry already anticipated).
// Because of (1), `alu_dut` below uses a plain (non-interface) port
// list -- see alu_if_tb.sv's header for how it is still connected
// through the `alu_if` interface instance via a named port map, and
// AUTOMATION_LOG.md (2026-08-24 entry) for the full summary.
//------------------------------------------------------------------------

`timescale 1ns/1ps

// 4-value packed enum -- default base type is `int` (2-state, 32-bit) but
// as a *port/interface field* it participates in the interface's 4-state
// `logic` signals, so X propagation still works if the DUT is unresolved
// or reset is not yet applied. Named values are far more readable than
// a bare 3'b010 in a waveform viewer or testbench trace.
typedef enum logic [2:0] {
    ALU_ADD = 3'b000,
    ALU_SUB = 3'b001,
    ALU_AND = 3'b010,
    ALU_OR  = 3'b011,
    ALU_XOR = 3'b100
} alu_op_e;

// Packed struct: bundles the three status flags into one typed field
// instead of three separate 1-bit ports. Packed (not just a SV struct)
// so it behaves like a single vector for waveform/VCD purposes and can
// be compared/assigned as a unit.
typedef struct packed {
    logic zero;
    logic carry;
    logic overflow;
} alu_flags_s;

// Interface bundling the full DUT<->TB connection for an 8-bit ALU.
// Using `logic` (not `wire`/`reg`) throughout, per SV convention, since
// `logic` can be driven by either continuous assignment or a procedural
// block and the simulator enforces single-driver rules regardless.
//
// See TOOLING NOTE (1) above: this interface's declaration compiles
// cleanly on Icarus 10.3 (verified); it is only *using it as a module
// port* (with or without a modport qualifier) that this build rejects.
// The modports below are the idiomatically-correct direction-checked
// views each side would use as its port type on a simulator with full
// interface-port support.
interface alu_if (input logic clk, input logic rst_n);
    logic  [7:0]   a, b;
    alu_op_e       op;
    logic          valid;
    logic  [7:0]   result;
    alu_flags_s    flags;
    logic          result_valid;

    // Intended DUT-side view (not usable as a port on this Icarus build
    // -- see TOOLING NOTE (1)): DUT reads stimulus fields as inputs,
    // drives result fields as outputs.
    modport dut (
        input  clk, rst_n, a, b, op, valid,
        output result, flags, result_valid
    );

    // Intended TB-side view (likewise not usable as a port here): mirror
    // image of the dut modport, from the same single point of
    // definition -- the value of interfaces over a raw port list is
    // that both sides' views are generated from one declaration instead
    // of two independently hand-maintained port lists that can silently
    // drift out of sync.
    modport tb (
        input  clk, rst_n, result, flags, result_valid,
        output a, b, op, valid
    );
endinterface

// Synchronous ALU DUT. Plain (non-interface) port list -- see TOOLING
// NOTE (1) above for why; this is the workaround for Icarus 10.3's lack
// of interface-port support, not the intended final form. Registers its
// inputs and result one cycle later (a deliberately simple pipeline
// stage, not purely combinational) so the example also exercises
// `result_valid` as a one-cycle-delayed valid signal -- a common real
// pattern the testbench must handle correctly.
module alu_dut (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [7:0]  a,
    input  logic [7:0]  b,
    input  alu_op_e     op,
    input  logic        valid,
    output logic [7:0]  result,
    output alu_flags_s  flags,
    output logic        result_valid
);

    logic [7:0]  result_c;
    alu_flags_s  flags_c;
    logic [8:0]  add_ext, sub_ext; // 9-bit to catch carry/borrow

    // Combinational compute stage. Plain `always @*` -- see TOOLING
    // NOTE (2): `always_comb` does not compile on this Icarus build.
    always @* begin
        add_ext = {1'b0, a} + {1'b0, b};
        sub_ext = {1'b0, a} - {1'b0, b};

        // Plain `case` -- see TOOLING NOTE (3): `unique case` does not
        // compile on this Icarus build.
        case (op)
            ALU_ADD: result_c = add_ext[7:0];
            ALU_SUB: result_c = sub_ext[7:0];
            ALU_AND: result_c = a & b;
            ALU_OR:  result_c = a | b;
            ALU_XOR: result_c = a ^ b;
            default: result_c = 8'hxx; // unreachable given alu_op_e's
                                        // restricted value set, but kept
                                        // as an explicit safety default
        endcase

        flags_c.zero     = (result_c == 8'h00);
        flags_c.carry    = (op == ALU_ADD) ? add_ext[8] :
                            (op == ALU_SUB) ? sub_ext[8] : 1'b0;
        // Signed overflow: both operands same sign, result different sign
        // (only meaningful for ADD/SUB; 0 for logical ops)
        flags_c.overflow =
            (op == ALU_ADD) ? ((a[7] == b[7]) && (result_c[7] != a[7])) :
            (op == ALU_SUB) ? ((a[7] != b[7]) && (result_c[7] != a[7])) :
            1'b0;
    end

    // Registered (1-cycle-latency) output stage. Plain
    // `always @(posedge clk or negedge rst_n)` -- see TOOLING NOTE (2):
    // `always_ff` does not compile on this Icarus build. Per-field
    // struct reset assignment -- see TOOLING NOTE (4): the
    // `'{default: 1'b0}` assignment-pattern syntax does not compile on
    // this Icarus build.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result          <= 8'h00;
            flags.zero      <= 1'b0;
            flags.carry     <= 1'b0;
            flags.overflow  <= 1'b0;
            result_valid    <= 1'b0;
        end else begin
            result       <= result_c;
            flags        <= flags_c;
            result_valid <= valid;
        end
    end

endmodule
