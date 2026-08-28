//------------------------------------------------------------------------
// alu_sva_checker.sv
//
// Phase 2 example: "Basic SVA (assert property, immediate vs.
// concurrent)" -- the progress.md item after functional coverage
// (2026-08-26, second session). Reuses alu_dut from alu_if_and_dut.sv
// unmodified, exactly as every other Phase 2 ALU example does.
//
// TOOLING FINDING (this session, 2026-08-28, confirmed with minimal
// standalone repros in /tmp/repro/ against the genuine pinned Icarus
// Verilog 10.3 toolchain (tools/setup_iverilog.sh) before being treated
// as established -- see notes/2026-08-28-sva-immediate-vs-concurrent-
// assertions.md for full repro listings, captured compiler output, and
// a secondary data point from Icarus Verilog 12.0):
//
//   Neither assertion flavor is implemented on this build:
//     - Immediate assertions (`assert (expr) else action;`, and the
//       `assert #0 (...)` variant) fail to compile: "sorry: Simple
//       immediate assertion statements not implemented." This
//       re-confirms the 2026-08-23 finding rather than assuming it still
//       holds.
//     - Concurrent assertions (`assert property (...)`, and even a
//       standalone `property ... endproperty` block on its own) also
//       fail, with an explicit "sorry: concurrent_assertion_item not
//       supported" message.
//   This is a clean, total gap (like 2026-08-26's randomize()/covergroup
//   findings), not a partial-support nuance -- so, exactly as those
//   examples did, this file demonstrates the underlying CONCEPT (a
//   dedicated, DUT-adjacent assertion-style checker, separate from
//   stimulus generation -- see notes file Section 1's last bullet for
//   why that separation matters, independent of concrete syntax) using
//   the `if (!cond) $error(...)` idiom this repo has used as the
//   immediate-assertion substitute since 2026-08-23, rather than native
//   `assert`/`assert property` syntax.
//
// TWO FURTHER TOOLING GAPS found while building this file (both new
// today, both confirmed by the compiler's own message rather than
// assumed): (1) a `function automatic void` with `output` arguments is
// rejected ("Function arguments must be input ports" -- Icarus 10.3
// functions apparently must be single-return-value only); worked around
// by declaring alu_ref_model as a `task automatic` instead, which does
// accept output arguments. (2) `enum_value.name()` used as a `$error`
// format argument is rejected ("Enumeration method name() is not
// currently supported in this context (self-determined)"); worked
// around by printing the raw enum-underlying value with %0d instead.
//
// WHAT MAKES THIS DIFFERENT FROM PRIOR ALU EXAMPLES: every earlier
// Phase 2 file (alu_if_tb.sv, alu_oop_tb_components.sv,
// alu_manual_constrained_random.sv, alu_manual_functional_coverage.sv)
// embeds its correctness checks inline within a stimulus-driving
// testbench. This file instead structures checking as a SEPARATE
// concern (the apply_and_check task below focuses purely on comparing
// DUT outputs to an independent reference model; a real assertion-based
// verification environment would express this as a `bind`-attached
// checker module or a set of `assert property` statements living
// alongside the DUT, decoupled entirely from whatever testbench drives
// stimulus) -- the architectural point Phase 3 (layered testbench
// architecture) will formalize further.
//------------------------------------------------------------------------

`timescale 1ns/1ps

module alu_sva_checker_tb;

    logic        clk = 0;
    logic        rst_n;
    logic [7:0]  a, b;
    alu_op_e     op;
    logic        valid;
    logic [7:0]  result;
    alu_flags_s  flags;
    logic        result_valid;

    always #5 clk = ~clk;

    alu_dut dut (
        .clk(clk), .rst_n(rst_n),
        .a(a), .b(b), .op(op), .valid(valid),
        .result(result), .flags(flags), .result_valid(result_valid)
    );

    int checks_run    = 0;
    int checks_passed = 0;

    // -------------------------------------------------------------
    // Independent reference model / "checker". See file header for
    // why the formulations below deliberately do NOT reuse alu_dut's
    // own internal expressions (a shared bug in "the obvious way to
    // compute this" would otherwise silently cancel out between DUT
    // and checker, exactly the failure mode an independent reference
    // model exists to avoid -- the same principle already used for
    // sync_fifo_directed_tb.v's independent reference queue,
    // 2026-08-23).
    // -------------------------------------------------------------
    task automatic alu_ref_model(
        input  logic [7:0] a_in, b_in,
        input  alu_op_e    op_in,
        output logic [7:0] exp_result,
        output logic        exp_zero,
        output logic        exp_carry,
        output logic        exp_overflow
    );
        logic signed [15:0] true_wide; // full-precision signed result,
                                        // no truncation -- used to detect
                                        // overflow by comparing against
                                        // the (possibly-truncated)
                                        // 8-bit signed result below
        begin
            case (op_in)
                ALU_ADD: begin
                    exp_result = a_in + b_in; // natural 8-bit wraparound
                    // Unsigned carry via comparison against the
                    // complement, not via a widened 9-bit add (that is
                    // the DUT's approach -- see add_ext[8] in
                    // alu_if_and_dut.sv).
                    exp_carry  = (a_in > (8'hFF - b_in));
                    true_wide  = $signed({{8{a_in[7]}}, a_in}) +
                                 $signed({{8{b_in[7]}}, b_in});
                    exp_overflow = (true_wide !=
                                    $signed({{8{exp_result[7]}}, exp_result}));
                end
                ALU_SUB: begin
                    exp_result = a_in - b_in; // natural 8-bit wraparound
                    // Unsigned borrow via direct magnitude comparison,
                    // not via a widened 9-bit subtract (the DUT's
                    // sub_ext[8] approach).
                    exp_carry  = (a_in < b_in);
                    true_wide  = $signed({{8{a_in[7]}}, a_in}) -
                                 $signed({{8{b_in[7]}}, b_in});
                    exp_overflow = (true_wide !=
                                    $signed({{8{exp_result[7]}}, exp_result}));
                end
                ALU_AND: begin
                    exp_result = a_in & b_in;
                    exp_carry = 1'b0; exp_overflow = 1'b0;
                end
                ALU_OR: begin
                    exp_result = a_in | b_in;
                    exp_carry = 1'b0; exp_overflow = 1'b0;
                end
                ALU_XOR: begin
                    exp_result = a_in ^ b_in;
                    exp_carry = 1'b0; exp_overflow = 1'b0;
                end
                default: begin
                    exp_result = 8'hxx; exp_carry = 1'bx; exp_overflow = 1'bx;
                end
            endcase
            exp_zero = (exp_result == 8'h00);
        end
    endtask

    // Remembers the operands/op used for the transaction currently in
    // flight, so the checker (running one cycle later, once
    // result_valid rises) checks against the SAME inputs that produced
    // the DUT's registered output -- not whatever a, b, op happen to
    // hold combinationally at check time.
    logic [7:0] a_q, b_q;
    alu_op_e    op_q;

    // Applies one ALU operation, waits for the registered result, then
    // checks it -- structured as a standalone checker step, deliberately
    // separate from any notion of "generate the next random stimulus"
    // (see file header). `corrupt` deliberately feeds the checker a
    // wrong expected value (the DUT and its actual inputs are untouched)
    // to prove the checks really do fire, not just always pass -- mirrors
    // sync_fifo_directed_tb.v's deliberate illegal-push/illegal-pop
    // checks (2026-08-23).
    task automatic apply_and_check(
        input logic [7:0] a_val, b_val,
        input alu_op_e    op_val,
        input string       label,
        input bit          corrupt = 1'b0
    );
        logic [7:0] exp_result, corrupted_result;
        logic        exp_zero, exp_carry, exp_overflow;
        begin
            @(posedge clk);
            a <= a_val; b <= b_val; op <= op_val; valid <= 1'b1;
            a_q <= a_val; b_q <= b_val; op_q <= op_val;

            @(posedge clk);
            valid <= 1'b0;

            // Give the registered outputs one delta cycle to settle
            // before sampling them (they were clocked on the edge we
            // just crossed).
            #1;

            checks_run++;
            if (!(result_valid === 1'b1))
                $error("[%0t] %s: expected result_valid=1, got %0b",
                        $time, label, result_valid);

            alu_ref_model(a_q, b_q, op_q, exp_result, exp_zero, exp_carry, exp_overflow);

            if (corrupt) begin
                // Deliberately wrong expected value -- injected into the
                // CHECK, not into the DUT -- so this check is guaranteed
                // to fail. Flips every bit of the correct result so it
                // can never accidentally match by chance.
                corrupted_result = ~exp_result;
                if (!(result === corrupted_result))
                    $error("[%0t] %s: EXPECTED-FAIL (deliberate): result=%0h did not match deliberately-wrong expected=%0h (real expected was %0h) -- this failure is correct and proves the checker works",
                            $time, label, result, corrupted_result, exp_result);
            end else begin
                if (!(result === exp_result))
                    $error("[%0t] %s: result mismatch: dut=%0h expected=%0h (a=%0h b=%0h op_code=%0d)",
                            $time, label, result, exp_result, a_q, b_q, op_q);
                if (!(flags.zero === exp_zero))
                    $error("[%0t] %s: zero flag mismatch: dut=%0b expected=%0b",
                            $time, label, flags.zero, exp_zero);
                if (!(flags.carry === exp_carry))
                    $error("[%0t] %s: carry flag mismatch: dut=%0b expected=%0b",
                            $time, label, flags.carry, exp_carry);
                if (!(flags.overflow === exp_overflow))
                    $error("[%0t] %s: overflow flag mismatch: dut=%0b expected=%0b",
                            $time, label, flags.overflow, exp_overflow);
                checks_passed++;
            end
        end
    endtask

    initial begin
        $dumpfile("alu_sva_checker_wave.vcd");
        $dumpvars(0, alu_sva_checker_tb);

        rst_n = 0; a = 0; b = 0; op = ALU_ADD; valid = 0;
        repeat (2) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        // --- ADD: normal, carry, zero-result, signed overflow ---
        apply_and_check(8'h05, 8'h03, ALU_ADD, "ADD normal (5+3=8)");
        apply_and_check(8'hFF, 8'h01, ALU_ADD, "ADD wrap+carry (0xFF+1=0x00, carry)");
        apply_and_check(8'h00, 8'h00, ALU_ADD, "ADD zero result");
        apply_and_check(8'h7F, 8'h01, ALU_ADD, "ADD signed overflow (MAX_POS+1)");
        apply_and_check(8'h80, 8'h80, ALU_ADD, "ADD signed overflow (MIN_NEG+MIN_NEG)");

        // --- SUB: normal, borrow, zero result, signed overflow ---
        apply_and_check(8'h08, 8'h03, ALU_SUB, "SUB normal (8-3=5)");
        apply_and_check(8'h00, 8'h01, ALU_SUB, "SUB borrow (0-1=0xFF, borrow)");
        apply_and_check(8'h42, 8'h42, ALU_SUB, "SUB zero result");
        apply_and_check(8'h80, 8'h01, ALU_SUB, "SUB signed overflow (MIN_NEG-1)");
        apply_and_check(8'h7F, 8'hFF, ALU_SUB, "SUB signed overflow (MAX_POS-(-1))");

        // --- Logical ops: no carry/overflow possible ---
        apply_and_check(8'hF0, 8'h0F, ALU_AND, "AND disjoint bits -> 0");
        apply_and_check(8'hF0, 8'h0F, ALU_OR,  "OR disjoint bits -> 0xFF");
        apply_and_check(8'hAA, 8'hFF, ALU_XOR, "XOR with all-ones -> complement");
        apply_and_check(8'h00, 8'h00, ALU_AND, "AND zero result");

        // --- Deliberate expected-fail: proves the checker actually
        //     catches a wrong result, not just that it always passes.
        apply_and_check(8'h10, 8'h20, ALU_ADD, "deliberate corrupted-expectation check", 1'b1);

        $display("--------------------------------------------------------");
        $display("Total checks = %0d, passed = %0d, deliberate-fail cases = 1",
                  checks_run, checks_passed);
        if (checks_passed == checks_run - 1)
            $display("PASS: all real checks matched the independent reference model; the one deliberate corrupted-expectation case correctly failed above.");
        else
            $display("FAIL: unexpected number of passing checks -- investigate.");
        $finish;
    end

endmodule
