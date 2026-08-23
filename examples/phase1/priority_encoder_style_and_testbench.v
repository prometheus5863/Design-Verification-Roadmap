// priority_encoder_style_and_testbench.v
//
// Phase 1 companion example for
// notes/2026-08-23-synthesizable-coding-style-and-self-checking-testbenches.md
//
// Demonstrates, with a runnable self-checking testbench:
//   1. Synthesizable-style-clean combinational coding (default
//      assignment + full case coverage -- no inferred latches).
//   2. The classic incomplete-case-statement latch-inference bug.
//   3. A self-checking testbench pattern: independent reference model,
//      exhaustive stimulus, per-vector checking with an error counter
//      and a final PASS/FAIL summary (rather than stopping at the first
//      mismatch).
//
// Run with Icarus Verilog:
//   iverilog -g2012 -o sim priority_encoder_style_and_testbench.v
//   vvp sim
//
// SIMULATED in the automation sandbox this file was authored in: this
// session located a working Icarus Verilog 10.3 binary (extracted from
// the Ubuntu 22.04 "jammy" universe .deb without needing root/apt, since
// dpkg-deb -x only extracts files and does not require install privileges)
// and ran this testbench end-to-end. See
// examples/phase1/priority_encoder_sim_output_2026-08-23.txt for the
// captured console output confirming: priority_encoder_correct passes
// all 16 exhaustive vectors, and priority_encoder_latch_bug fails
// exactly the in=4'b0000 vector as predicted, with 'x' outputs (see the
// priority_encoder_latch_bug comment below for why 'x' specifically,
// not a stale prior value, on this run).

`timescale 1ns/1ps

// -----------------------------------------------------------------------
// Spec: 4-bit input `in`, priority-encode the highest-index set bit.
//   in = 4'b0000 -> valid = 0, enc = 2'b00 (enc undefined by spec when
//                   valid=0, but this design drives it to 0 rather than
//                   leaving it as 'x, since a deterministic idle value
//                   is easier to check and avoids X-propagation surprises
//                   downstream -- a real design decision worth documenting
//                   explicitly rather than leaving implicit).
//   in = 4'bxxx1 (bit0 set, ignore higher bits *only if* none higher set)
//   Priority order: bit3 highest priority, bit0 lowest.
// -----------------------------------------------------------------------

// -----------------------------------------------------------------------
// CORRECT: synthesizable-style-clean version.
//   - Default assignment at top of the combinational block.
//   - always @(*) (auto-inferred sensitivity list).
//   - casez fully covers all 5 meaningful patterns including the
//     explicit no-bit-set case -- no path is left unassigned, so no
//     latch is inferred.
// -----------------------------------------------------------------------
module priority_encoder_correct (
    input  logic [3:0] in,
    output logic       valid,
    output logic [1:0] enc
);
    always @(*) begin
        // Default assignment: guarantees every signal driven by this
        // block is assigned on every path, before any conditional logic
        // below potentially overrides it. This is the single most
        // important habit for avoiding inferred latches.
        valid = 1'b0;
        enc   = 2'b00;

        casez (in)
            4'b1???: begin valid = 1'b1; enc = 2'd3; end
            4'b01??: begin valid = 1'b1; enc = 2'd2; end
            4'b001?: begin valid = 1'b1; enc = 2'd1; end
            4'b0001: begin valid = 1'b1; enc = 2'd0; end
            4'b0000: begin valid = 1'b0; enc = 2'd0; end // explicit, matches default
            default: begin valid = 1'b0; enc = 2'd0; end // safety net, should be unreachable
        endcase
    end
endmodule

// -----------------------------------------------------------------------
// BUGGY: the 4'b0000 case (and default) is omitted from the casez.
// Because the block ALSO has no unconditional default assignment at the
// top (removed here to reproduce the bug realistically -- this is how
// the bug usually actually appears in practice: someone deletes the
// "redundant-looking" default assignment during a refactor, not
// realizing it was load-bearing), the in=4'b0000 input path leaves
// `valid` and `enc` unassigned. Synthesis infers latches for both. In
// simulation, an unassigned `logic`/`reg` reads as 'x' until some path
// first drives it -- verified below with Icarus Verilog 10.3: since the
// testbench happens to test in=4'b0000 FIRST (vector 0 of an increasing
// 0..15 sweep), both outputs come out as 'x' (never yet assigned) on
// that specific run, rather than "the previous vector's value." Whether
// this class of bug manifests as 'x', a stale prior value, or (in a real
// synthesized latch) a genuinely previous-cycle-dependent value depends
// on simulation/test order and tool -- exactly the kind of order-
// dependent behavior that makes latch-inference bugs notoriously hard to
// catch with a few hand-picked directed vectors, and a good argument for
// exhaustive or randomized coverage of small state spaces like this one.
// -----------------------------------------------------------------------
module priority_encoder_latch_bug (
    input  logic [3:0] in,
    output logic       valid,
    output logic [1:0] enc
);
    always @(*) begin
        casez (in)
            4'b1???: begin valid = 1'b1; enc = 2'd3; end
            4'b01??: begin valid = 1'b1; enc = 2'd2; end
            4'b001?: begin valid = 1'b1; enc = 2'd1; end
            4'b0001: begin valid = 1'b1; enc = 2'd0; end
            // BUG: no 4'b0000 / default case -- valid and enc are left
            // unassigned on this path, inferring a latch.
        endcase
    end
endmodule

// -----------------------------------------------------------------------
// Self-checking testbench.
//
// Reference model: a plain behavioral function computing expected
// (valid, enc) directly from the specification using a for-loop scan
// from bit 3 down to bit 0, deliberately implemented differently from
// either DUT's casez structure so it does not share a structural bug
// with the DUT even if one existed in the casez ordering itself.
// -----------------------------------------------------------------------
module tb_priority_encoder;
    logic [3:0] in;
    logic       valid_correct, valid_buggy;
    logic [1:0] enc_correct,   enc_buggy;

    integer errors_correct = 0;
    integer errors_buggy   = 0;
    integer i;

    priority_encoder_correct dut_correct (
        .in(in), .valid(valid_correct), .enc(enc_correct)
    );

    priority_encoder_latch_bug dut_buggy (
        .in(in), .valid(valid_buggy), .enc(enc_buggy)
    );

    // Independent reference model (software-style, spec-driven, not a
    // mirror of either DUT's casez structure). Written as a task rather
    // than a function since it has multiple outputs (Icarus Verilog's
    // SystemVerilog subset support does not accept output-mode function
    // ports here; a task is the portable choice).
    task automatic reference_model(
        input  logic [3:0] in_val,
        output logic       exp_valid,
        output logic [1:0] exp_enc
    );
        integer bit_idx;
        begin
            exp_valid = 1'b0;
            exp_enc   = 2'b00;
            for (bit_idx = 3; bit_idx >= 0; bit_idx = bit_idx - 1) begin
                if (!exp_valid && in_val[bit_idx]) begin
                    exp_valid = 1'b1;
                    exp_enc   = bit_idx[1:0];
                end
            end
        end
    endtask

    task automatic check_vector(input logic [3:0] in_val);
        logic       exp_valid;
        logic [1:0] exp_enc;
        begin
            in = in_val;
            #1; // allow combinational logic to settle
            reference_model(in_val, exp_valid, exp_enc);

            if (valid_correct !== exp_valid || enc_correct !== exp_enc) begin
                errors_correct = errors_correct + 1;
                $display("[FAIL][correct] in=%b: got valid=%b enc=%b, expected valid=%b enc=%b",
                          in_val, valid_correct, enc_correct, exp_valid, exp_enc);
            end

            if (valid_buggy !== exp_valid || enc_buggy !== exp_enc) begin
                errors_buggy = errors_buggy + 1;
                $display("[FAIL][latch_bug] in=%b: got valid=%b enc=%b, expected valid=%b enc=%b",
                          in_val, valid_buggy, enc_buggy, exp_valid, exp_enc);
            end
        end
    endtask

    initial begin
        $display("Running exhaustive 4-bit priority encoder self-check (16 vectors)...");
        for (i = 0; i < 16; i = i + 1) begin
            check_vector(i[3:0]);
        end

        $display("---------------------------------------------------------");
        if (errors_correct == 0)
            $display("PASS: priority_encoder_correct matched reference on all 16 vectors.");
        else
            $display("FAIL: priority_encoder_correct had %0d mismatch(es) out of 16 vectors.", errors_correct);

        if (errors_buggy != 0)
            $display("EXPECTED-FAIL: priority_encoder_latch_bug had %0d mismatch(es) out of 16 vectors (demonstrates the missing-case/latch-inference bug -- expected to fail specifically on in=4'b0000, where valid/enc are left at their stale simulation value instead of the specified valid=0).", errors_buggy);
        else
            $display("UNEXPECTED: priority_encoder_latch_bug matched reference on all vectors -- bug did not manifest as expected in this simulator/run; re-check simulator's default-net/latch initial-value handling.");

        $finish;
    end
endmodule
