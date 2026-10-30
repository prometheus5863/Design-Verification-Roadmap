// examples/phase6_uvm_checker_bind/uart_checker_bind_top.v
//
// THE BINDING LAYER: the DUT and the black-box protocol checker on the same
// pins, with the checker's verdict exported as ORDINARY SIGNALS so the UVM
// environment can read it.
//
// This closes the item ranked first in the 2026-10-29 log entry ("BIND THE
// CHECKER INTO THE uvm-python ENVIRONMENT -- the direct continuation, blocked
// only on running tools/setup_cocotb.sh").  The block was real: the stack
// installed and verified today in one shell call (tools/setup_cocotb.sh,
// RESULT: PASS, all 12 checks).
//
// ---------------------------------------------------------------------------
// WHY A WRAPPER AND NOT SystemVerilog `bind`
// ---------------------------------------------------------------------------
// `bind` is the right construct and Icarus Verilog 10.3 does not have it --
// the same toolchain fact that made the checker procedural rather than SVA in
// the first place.  A wrapper that instantiates both on one pin set is the
// Verilog-95-compatible equivalent for a BLACK-BOX checker specifically: the
// checker refers to nothing but the module's pins, so there is nothing for
// `bind`'s hierarchical scope access to provide that the wrapper cannot.  A
// white-box checker could not be bound this way, and the FORMAL blocks inside
// rtl/uart_controller.v are the example of one that could not.
//
// ---------------------------------------------------------------------------
// WHY THE PORT LIST IS COPIED EXACTLY, AND WHAT CHECKS THAT
// ---------------------------------------------------------------------------
// The port list below is uart_controller's, name for name and width for
// width, so that TOPLEVEL can be switched from uart_controller to this module
// WITHOUT TOUCHING THE PYTHON TESTBENCH: examples/phase6_uvm_crv_uart's
// driver and monitor reach dut.psel, dut.prdata and so on, and they resolve
// against this wrapper identically.  The testbench is therefore IMPORTED by
// the bound test rather than copied, which is the only way the two can be
// known to be driving the same stimulus.
//
// A copied port list is a claim that can rot, so it is not left as a comment:
// tools/checker_bind_port_audit.py parses both module headers and fails if
// they ever disagree in name, direction, width or order.
//
// ---------------------------------------------------------------------------
// WHY THE VERDICT IS EXPORTED AS REGS AND NOT READ FROM THE CHECKER'S ARRAYS
// ---------------------------------------------------------------------------
// The checker keeps its per-rule counts in `integer viol [0:13]` and
// `integer fired [0:13]`, plus the two scalars `viol_i1`/`fired_i1` for the
// fifteenth rule.  cocotb's access to a Verilog `integer` ARRAY through the
// Icarus VPI is not something this repository has established, and a binding
// whose verdict channel might silently fail to resolve is a binding that
// could report green because it read nothing.  So the aggregation happens
// HERE, in Verilog, where hierarchical reference into the instance is
// ordinary, and what Python reads is a plain 32-bit reg and two 15-bit
// vectors.  `chk_alive` exists for exactly the failure the paragraph above
// describes: it counts clocks and so is nonzero in any run that ran, which
// makes "I read a zero because nothing was there" distinguishable from "I
// read a zero because there were no violations".
//
// THE AGGREGATION IS UNCONDITIONAL AND COMBINATIONAL-IN-INTENT (it is a
// clocked always block only so Python sees a settled value at a clock edge).
// It deliberately does NOT use the checker's own `report` task: a task
// cannot be called from cocotb, and more importantly the task both PRINTS
// and SUMS.  Re-deriving the sum here from the same arrays means the UVM
// verdict and the Verilog transcript are two independent readings of one
// state, so a disagreement between them is detectable -- and
// examples/phase6_uvm_checker_bind/run_mutation_tests.sh checks that they
// agree on every mutant.

`timescale 1ns / 1ps

module uart_checker_bind_top (
    input  wire       clk,
    input  wire       rst_n,

    // APB-lite register interface
    input  wire [3:0] paddr,
    input  wire [7:0] pwdata,
    output wire [7:0] prdata,
    input  wire       pwrite,
    input  wire       psel,
    input  wire       penable,
    output wire       pready,

    // Serial lines
    output wire       tx,
    input  wire       rx,

    // Level interrupt, active high
    output wire       irq
);

    localparam N_RULES_TOTAL = 15;   // 14 indexed + I1

    uart_controller u_dut (
        .clk     (clk),
        .rst_n   (rst_n),
        .paddr   (paddr),
        .pwdata  (pwdata),
        .prdata  (prdata),
        .pwrite  (pwrite),
        .psel    (psel),
        .penable (penable),
        .pready  (pready),
        .tx      (tx),
        .rx      (rx),
        .irq     (irq)
    );

    uart_protocol_checker u_chk (
        .clk     (clk),
        .rst_n   (rst_n),
        .paddr   (paddr),
        .pwdata  (pwdata),
        .prdata  (prdata),
        .pwrite  (pwrite),
        .psel    (psel),
        .penable (penable),
        .pready  (pready),
        .tx      (tx),
        .rx      (rx),
        .irq     (irq)
    );

    // ---- the exported verdict ------------------------------------------
    reg [31:0] chk_viol_total;
    reg [31:0] chk_viol_stable;
    reg [31:0] chk_viol_reconfig;
    reg [31:0] chk_frames;
    reg [31:0] chk_frames_reconfig;
    reg [31:0] chk_alive;
    reg [N_RULES_TOTAL-1:0] chk_rule_viol;    // bit r set: rule r has fired
    reg [N_RULES_TOTAL-1:0] chk_rule_eval;    // bit r set: rule r evaluated
    reg [N_RULES_TOTAL-1:0] chk_rule_na;      // bit r set: N/A in the v1 scope

    integer i;
    integer acc;
    integer acc_s;
    integer acc_r;

    initial begin
        chk_viol_total      = 32'd0;
        chk_viol_stable     = 32'd0;
        chk_viol_reconfig   = 32'd0;
        chk_frames          = 32'd0;
        chk_frames_reconfig = 32'd0;
        chk_alive           = 32'd0;
        chk_rule_viol  = {N_RULES_TOTAL{1'b0}};
        chk_rule_eval  = {N_RULES_TOTAL{1'b0}};
        chk_rule_na    = {N_RULES_TOTAL{1'b0}};
    end

    always @(posedge clk) begin
        chk_alive = chk_alive + 32'd1;
        acc = 0; acc_s = 0; acc_r = 0;
        for (i = 0; i < 14; i = i + 1) begin
            acc   = acc   + u_chk.viol[i];
            acc_s = acc_s + u_chk.viol_stable[i];
            acc_r = acc_r + u_chk.viol_reconfig[i];
            // chk_rule_viol is the STABLE-frame verdict per rule: a rule
            // that only fired inside a RECONFIGURED frame fired outside its
            // own domain of validity, and the count of those is exported
            // separately rather than folded in here.  See the exclusion-class
            // comment in checkers/uart_protocol_checker.v (2026-10-30).
            chk_rule_viol[i] = (u_chk.viol_stable[i] != 0);
            chk_rule_eval[i] = (u_chk.fired[i] != 0);
            chk_rule_na[i]   = u_chk.na[i];
        end
        acc   = acc   + u_chk.viol_i1;
        acc_s = acc_s + u_chk.viol_i1_stable;
        acc_r = acc_r + u_chk.viol_i1_reconfig;
        chk_rule_viol[14] = (u_chk.viol_i1_stable != 0);
        chk_rule_eval[14] = (u_chk.fired_i1 != 0);
        chk_rule_na[14]   = 1'b0;
        chk_viol_total      = acc[31:0];
        chk_viol_stable     = acc_s[31:0];
        chk_viol_reconfig   = acc_r[31:0];
        chk_frames          = u_chk.frames[31:0];
        chk_frames_reconfig = u_chk.frames_reconfig[31:0];
    end

endmodule
