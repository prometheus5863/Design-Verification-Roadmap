// shift_register_blocking_vs_nonblocking.v
//
// Phase 1 companion example for
// notes/2026-08-22-verilog-fundamentals-blocking-vs-nonblocking.md
//
// Demonstrates, with a runnable testbench, the functional difference
// between a correctly-coded (non-blocking) 2-stage shift register and a
// buggy (blocking) version of "the same" design.
//
// Run with Icarus Verilog:
//   iverilog -g2001 -o sim shift_register_blocking_vs_nonblocking.v
//   vvp sim
//
// NOT simulated in the automation sandbox this file was authored in (no
// iverilog available there) -- see the accompanying notes file for the
// hand-derived expected behavior. Intended to be run and checked locally.

`timescale 1ns/1ps

// -----------------------------------------------------------------------
// CORRECT: non-blocking assignments -- both flops sample the pre-edge
// value of their input, giving a true 2-cycle shift register.
// -----------------------------------------------------------------------
module shift_reg_correct (
    input  logic clk,
    input  logic rst_n,
    input  logic d,
    output logic q1,
    output logic q2
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q1 <= 1'b0;
            q2 <= 1'b0;
        end else begin
            q1 <= d;
            q2 <= q1;
        end
    end
endmodule

// -----------------------------------------------------------------------
// BUGGY: blocking assignments used inside a clocked always block --
// collapses the intended 2-cycle delay into 1 cycle, because the second
// statement reads the value q1 was just assigned in the same edge.
// -----------------------------------------------------------------------
module shift_reg_buggy (
    input  logic clk,
    input  logic rst_n,
    input  logic d,
    output logic q1,
    output logic q2
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q1 = 1'b0;
            q2 = 1'b0;
        end else begin
            q1 = d;
            q2 = q1;   // BUG: sees the new q1, not the old one
        end
    end
endmodule

// -----------------------------------------------------------------------
// Directed, self-checking testbench.
//
// Reference model: a plain behavioral queue (software model, not RTL)
// tracking what q2 of a CORRECT 2-stage shift register should be, so the
// check does not depend on either DUT variant's (possibly buggy)
// internal state.
// -----------------------------------------------------------------------
module tb_shift_register;
    logic clk = 0;
    logic rst_n;
    logic d;
    logic q1_correct, q2_correct;
    logic q1_buggy,   q2_buggy;

    // Software reference model for the CORRECT 2-cycle-delayed q2
    logic ref_stage1, ref_stage2;

    integer errors_correct = 0;
    integer errors_buggy_matches_correct = 0;  // expected to be > 0:
                                                // demonstrates the buggy
                                                // version DIVERGES from
                                                // correct behavior
    integer cycle = 0;

    shift_reg_correct dut_correct (
        .clk(clk), .rst_n(rst_n), .d(d), .q1(q1_correct), .q2(q2_correct)
    );

    shift_reg_buggy dut_buggy (
        .clk(clk), .rst_n(rst_n), .d(d), .q1(q1_buggy), .q2(q2_buggy)
    );

    // 10 ns clock period
    always #5 clk = ~clk;

    // Reference-model update: mirrors the CORRECT non-blocking timing,
    // i.e. this always block is itself written the correct way, since it
    // exists to be a trustworthy oracle, not the thing under test.
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ref_stage1 <= 1'b0;
            ref_stage2 <= 1'b0;
        end else begin
            ref_stage1 <= d;
            ref_stage2 <= ref_stage1;
        end
    end

    initial begin
        rst_n = 0;
        d = 0;
        @(negedge clk);
        rst_n = 1;

        // Drive a pseudo-random-looking but fixed, reproducible sequence
        // (directed test -- Phase 2 will introduce constrained-random
        // stimulus via SystemVerilog randomize()/rand, which is the
        // natural next step up from this style of test).
        repeat (12) begin
            @(negedge clk);
            d = $random;
            cycle = cycle + 1;

            // check one cycle after the NEXT posedge, once values have
            // settled, comparing against the software reference model
            #1;
        end

        // Let the pipe drain, then report
        repeat (3) @(negedge clk);

        $display("---------------------------------------------------------");
        $display("Test complete after %0d driven cycles.", cycle);
        $display("errors_correct (DUT vs reference model)      = %0d",
                  errors_correct);
        $display("cycles where BUGGY q2 != CORRECT/reference q2 = %0d",
                  errors_buggy_matches_correct);
        if (errors_correct == 0)
            $display("PASS: shift_reg_correct matches the reference model on every checked cycle.");
        else
            $display("FAIL: shift_reg_correct diverged from the reference model -- unexpected.");

        if (errors_buggy_matches_correct > 0)
            $display("EXPECTED: shift_reg_buggy diverges from correct behavior, demonstrating the blocking-assignment bug described in the accompanying notes.");
        else
            $display("UNEXPECTED: shift_reg_buggy matched correct behavior on every cycle -- re-check the test sequence (a bug that only manifests on toggling data can be masked by an unlucky constant-data sequence).");

        $finish;
    end

    // Continuous self-checking, one delta cycle after each posedge so all
    // non-blocking updates in this time step have settled.
    always @(posedge clk) begin
        #0.1;
        if (rst_n) begin
            if (q2_correct !== ref_stage2) begin
                errors_correct = errors_correct + 1;
                $display("[%0t] MISMATCH (correct DUT): q2_correct=%b ref_stage2=%b",
                          $time, q2_correct, ref_stage2);
            end
            if (q2_buggy !== ref_stage2) begin
                errors_buggy_matches_correct = errors_buggy_matches_correct + 1;
            end
        end
    end

endmodule
