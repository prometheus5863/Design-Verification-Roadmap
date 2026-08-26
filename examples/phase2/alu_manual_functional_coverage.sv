//------------------------------------------------------------------------
// alu_manual_functional_coverage.sv
//
// Phase 2 example: "Functional coverage (covergroup/coverpoint/cross)" --
// the next progress.md item after Randomization (2026-08-26 first
// session). Reuses alu_dut (alu_if_and_dut.sv), the scoreboard pattern,
// and the manual dist-like/randc-like generators from
// alu_manual_constrained_random.sv, all unmodified.
//
// TOOLING FINDING (this session, confirmed with a minimal standalone
// repro BEFORE committing to this file's design, per this repo's
// established practice -- see notes/2026-08-26-functional-coverage-covergroup-gap.md):
// `covergroup` is not implemented AT ALL on this Icarus Verilog 10.3
// build -- the parser does not even recognize the `covergroup` keyword
// ("syntax error" / "invalid module item" at the `covergroup` line
// itself, both at module scope and, by the same mechanism, inside a
// class). This is a bigger gap than any single missing piece found on
// 2026-08-23/24/25 (which had in-language workarounds for otherwise-
// working constructs) and matches the same category of finding as
// 2026-08-26's randomize()/constraint result: an entire IEEE 1800
// feature area absent, not partially supported.
//
// This file therefore demonstrates the SAME CONCEPTS -- coverpoints with
// bins, a cross between two coverpoints, an "at least N hits" bin-closure
// target, and using the resulting coverage percentage as a stopping
// criterion for random regeneration (the actual practical reason
// functional coverage exists: knowing when to STOP running random tests)
// -- via hand-written counters and an explicit coverage-driven simulation
// loop, clearly documented as a workaround, not presented as if it were
// a real covergroup. See notes/2026-08-26-functional-coverage-covergroup-gap.md, Section 3,
// for why this equivalence is faithful for simple bins/cross but does
// NOT reproduce real SV coverage features this hand-written version has
// no equivalent for: automatic bin-illegal/ignore_bins, transition bins,
// coverage sampling triggered by an event/clocking-block expression
// (sampling is just called explicitly here, after each transaction), or
// the `option.at_least`/`option.weight` per-bin configuration knobs.
//------------------------------------------------------------------------

`timescale 1ns/1ps

module alu_manual_functional_coverage_tb;

    // ---- Transaction (identical structure to alu_manual_constrained_random.sv) ----
    class alu_transaction;
        logic [7:0] a, b;
        logic [2:0] op_raw;

        function string op_name();
            case (op_raw)
                3'b000: op_name = "ALU_ADD";
                3'b001: op_name = "ALU_SUB";
                3'b010: op_name = "ALU_AND";
                3'b011: op_name = "ALU_OR";
                3'b100: op_name = "ALU_XOR";
                default: op_name = "ALU_?";
            endcase
        endfunction
    endclass

    // ---- Scoreboard (identical to alu_manual_constrained_random.sv) ----
    class alu_scoreboard;
        int checks = 0;
        int errors = 0;

        task predict(input logic [7:0] a, b, input logic [2:0] op_raw,
                     output logic [7:0] exp_result, output alu_flags_s exp_flags);
            logic [8:0] add_ext, sub_ext;
            add_ext = {1'b0, a} + {1'b0, b};
            sub_ext = {1'b0, a} - {1'b0, b};
            case (op_raw)
                3'b000: exp_result = add_ext[7:0];
                3'b001: exp_result = sub_ext[7:0];
                3'b010: exp_result = a & b;
                3'b011: exp_result = a | b;
                3'b100: exp_result = a ^ b;
                default: exp_result = 8'hxx;
            endcase
            exp_flags.zero  = (exp_result == 8'h00);
            exp_flags.carry = (op_raw == 3'b000) ? add_ext[8] :
                               (op_raw == 3'b001) ? sub_ext[8] : 1'b0;
            exp_flags.overflow =
                (op_raw == 3'b000) ? ((a[7] == b[7]) && (exp_result[7] != a[7])) :
                (op_raw == 3'b001) ? ((a[7] != b[7]) && (exp_result[7] != a[7])) :
                1'b0;
        endtask

        task check(input logic [7:0] a, b, input logic [2:0] op_raw,
                   input logic [7:0] actual_result, input alu_flags_s actual_flags,
                   input logic actual_result_valid, input int idx, input string opname);
            logic [7:0] exp_result;
            alu_flags_s exp_flags;
            predict(a, b, op_raw, exp_result, exp_flags);
            checks = checks + 1;
            if (actual_result_valid !== 1'b1) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s]: result_valid=%b, expected 1",
                          idx, opname, actual_result_valid);
            end else if (actual_result !== exp_result) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s]: result=%0d, expected %0d",
                          idx, opname, actual_result, exp_result);
            end else if (actual_flags !== exp_flags) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s]: flags={z,c,ovf}=%b, expected %b",
                          idx, opname, actual_flags, exp_flags);
            end
        endtask

        function void report();
            $display("------------------------------------------------------");
            $display("alu_scoreboard: %0d checks, %0d errors", checks, errors);
            if (errors == 0)
                $display("RESULT: ALL CHECKS PASSED");
            else
                $display("RESULT: %0d CHECK(S) FAILED", errors);
            $display("------------------------------------------------------");
        endfunction
    endclass

    // ---- Manual generators, reused unmodified from alu_manual_constrained_random.sv ----
    logic [7:0] corner_vals[0:4];
    int         corner_ptr;

    task shuffle_corners();
        int j;
        logic [7:0] tmp;
        for (int i = 4; i > 0; i = i - 1) begin
            j = $urandom_range(0, i);
            tmp = corner_vals[i];
            corner_vals[i] = corner_vals[j];
            corner_vals[j] = tmp;
        end
        corner_ptr = 0;
    endtask

    task next_corner_value(output logic [7:0] v);
        if (corner_ptr >= 5) shuffle_corners();
        v = corner_vals[corner_ptr];
        corner_ptr = corner_ptr + 1;
    endtask

    task weighted_op_select(output logic [2:0] op_raw);
        int r;
        r = $urandom_range(0, 6);
        if (r < 1)      op_raw = 3'b000;
        else if (r < 4) op_raw = 3'b001;
        else if (r < 5) op_raw = 3'b010;
        else if (r < 6) op_raw = 3'b011;
        else            op_raw = 3'b100;
    endtask

    // ---- Manual functional coverage model (this session's new content) ----
    //
    // coverpoint "op": 5 bins, one per opcode (ALU_ADD..ALU_XOR), goal:
    //   each bin hit at least MIN_HITS_OP times (mirrors a real
    //   `bins <name> = {value} ... option.at_least = N`).
    // coverpoint "a_corner": 3 bins categorizing the `a` operand --
    //   ZERO (a==0), MAX (a==255), MID (everything else) -- goal: each
    //   bin hit at least MIN_HITS_CORNER times.
    // cross "op_x_corner": all 5*3=15 legal (op, a_corner) combinations,
    //   goal: each combination hit at least once (a cross bin's default
    //   at_least is 1 in real SV coverage, unless overridden -- used as
    //   the realistic default here too).
    //
    // Bin-hit arrays are module-level (not class properties), per the
    // 2026-08-26 finding that unpacked arrays as class properties are
    // broken on this build (see alu_manual_constrained_random.sv header).
    // The cross is flattened to a 1-D array (index = op_raw*3 +
    // a_corner) rather than a 2-D unpacked array, since 2-D unpacked
    // arrays had not been exercised anywhere in this repo before today
    // and this sidesteps re-testing another untested construct for no
    // benefit -- flattening is also exactly what a real coverage tool's
    // internal bin storage does.
    localparam int NUM_OPS     = 5;
    localparam int NUM_CORNERS = 3;   // 0=ZERO, 1=MAX, 2=MID
    localparam int MIN_HITS_OP      = 8;
    localparam int MIN_HITS_CORNER  = 8;
    localparam int MIN_HITS_CROSS   = 1;

    int op_bin_hits[0:NUM_OPS-1];
    int corner_bin_hits[0:NUM_CORNERS-1];
    int cross_bin_hits[0:NUM_OPS*NUM_CORNERS-1];

    function int a_corner_of(logic [7:0] aval);
        if (aval == 8'h00)      a_corner_of = 0; // ZERO
        else if (aval == 8'hFF) a_corner_of = 1; // MAX
        else                     a_corner_of = 2; // MID
    endfunction

    task sample_coverage(input logic [2:0] op_raw, input logic [7:0] a_val);
        int corner_idx, cross_idx, op_idx;
        corner_idx = a_corner_of(a_val);
        op_idx     = op_raw;   // plain assignment (int <= logic[2:0]) --
                                // avoids the explicit int'(...) cast,
                                // which crashes the elaborator on this
                                // build (assert: elab_expr.cc:2630,
                                // "cast type and subject differ in
                                // signedness") -- see notes/2026-08-26-
                                // fn-coverage-*.md, Section 2, for the
                                // minimal repro that isolated this.
        cross_idx  = op_idx * NUM_CORNERS + corner_idx;
        op_bin_hits[op_raw]        = op_bin_hits[op_raw] + 1;
        corner_bin_hits[corner_idx] = corner_bin_hits[corner_idx] + 1;
        cross_bin_hits[cross_idx]   = cross_bin_hits[cross_idx] + 1;
    endtask

    function real coverpoint_op_pct();
        int hit;
        hit = 0;
        for (int i = 0; i < NUM_OPS; i = i + 1)
            if (op_bin_hits[i] >= MIN_HITS_OP) hit = hit + 1;
        coverpoint_op_pct = 100.0 * real'(hit) / real'(NUM_OPS);
    endfunction

    function real coverpoint_corner_pct();
        int hit;
        hit = 0;
        for (int i = 0; i < NUM_CORNERS; i = i + 1)
            if (corner_bin_hits[i] >= MIN_HITS_CORNER) hit = hit + 1;
        coverpoint_corner_pct = 100.0 * real'(hit) / real'(NUM_CORNERS);
    endfunction

    function real cross_op_corner_pct();
        int hit, total;
        hit = 0;
        total = NUM_OPS * NUM_CORNERS;
        for (int i = 0; i < total; i = i + 1)
            if (cross_bin_hits[i] >= MIN_HITS_CROSS) hit = hit + 1;
        cross_op_corner_pct = 100.0 * real'(hit) / real'(total);
    endfunction

    // Overall coverage = unweighted mean of the coverpoint/cross
    // percentages, matching a real covergroup's default (weight=1 per
    // coverpoint/cross unless overridden).
    function real overall_coverage_pct();
        overall_coverage_pct =
            (coverpoint_op_pct() + coverpoint_corner_pct() + cross_op_corner_pct()) / 3.0;
    endfunction

    logic clk = 0;
    logic rst_n;
    always #5 clk = ~clk; // 100 MHz

    logic [7:0] a, b, result;
    logic [2:0] op_raw;
    logic       valid, result_valid;
    alu_flags_s flags;

    alu_dut dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .a            (a),
        .b            (b),
        .op           (op_raw),
        .valid        (valid),
        .result       (result),
        .flags        (flags),
        .result_valid (result_valid)
    );

    alu_scoreboard sb;

    // Coverage-driven stopping criterion: keep generating random
    // transactions until either 100% overall coverage is reached OR a
    // hard cap is hit (the cap exists so a badly-tuned generator can't
    // hang the simulation forever -- exactly the same practical concern
    // that makes real regression coverage-closure reports include a
    // "did we actually converge, or time out" note).
    localparam int MAX_TRANSACTIONS = 4000;

    initial begin
        alu_transaction t;
        logic [7:0] sent_a, sent_b;
        logic [2:0] sent_op;
        int txn_count;
        int closure_txn_count;
        bit closed;

        $dumpfile("alu_manual_functional_coverage_wave.vcd");
        $dumpvars(0, alu_manual_functional_coverage_tb);

        corner_vals[0] = 8'h00;
        corner_vals[1] = 8'hFF;
        corner_vals[2] = 8'h80;
        corner_vals[3] = 8'h7F;
        corner_vals[4] = 8'h01;
        corner_ptr = 5;

        sb = new();
        closed = 0;
        closure_txn_count = -1;

        rst_n = 0; a = 0; b = 0; op_raw = 0; valid = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        for (txn_count = 0; txn_count < MAX_TRANSACTIONS; txn_count = txn_count + 1) begin
            if (closed) begin
                // Coverage goal already met -- stop generating new
                // stimulus. (Kept inside the same for-loop rather than
                // a `break`, since this repo has not exercised `break`
                // inside a `for` combined with everything else in this
                // file yet and there is no need to risk it for a cosmetic
                // change; the `if (!closed)` guard below is equivalent.)
            end else begin
                t = new();
                t.b = $urandom_range(0, 255);
                weighted_op_select(sent_op);
                t.op_raw = sent_op;

                // Same 1-in-4 corner-value draw rate as
                // alu_manual_constrained_random.sv (2026-08-26, first
                // session). A 1-in-2 rate was also tried this session
                // (see notes/2026-08-26-functional-coverage-covergroup-gap.md,
                // Section 4, for both measured results) on the theory
                // that the ZERO/MAX a_corner bins and their cross
                // combinations with every opcode are rare under uniform
                // `a` (each ~1/256) and might need more corner draws to
                // close reliably; measured coverage closure was reached
                // well within MAX_TRANSACTIONS at both rates (this
                // build's `$urandom` is deterministically seeded, so
                // this is one fixed draw sequence, not a statistical
                // claim about the rate in general), so the rate was left
                // at 1-in-4 for consistency with the established
                // convention rather than changed without a measured need
                // to.
                if ((txn_count % 4) == 3) begin
                    next_corner_value(sent_a);
                    t.a = sent_a;
                end else begin
                    sent_a = $urandom_range(0, 255);
                    t.a = sent_a;
                end
                sent_b = t.b;

                a <= sent_a; b <= sent_b; op_raw <= sent_op; valid <= 1'b1;
                @(posedge clk);
                valid <= 1'b0;
                @(posedge clk);

                sb.check(sent_a, sent_b, sent_op, result, flags, result_valid,
                          txn_count, t.op_name());
                sample_coverage(sent_op, sent_a);

                if (overall_coverage_pct() >= 100.0) begin
                    closed = 1;
                    closure_txn_count = txn_count + 1;
                end
            end
        end

        sb.report();
        $display("------------------------------------------------------");
        $display("FUNCTIONAL COVERAGE REPORT (manual model -- covergroup unavailable)");
        $display("  coverpoint op         : %0.1f%% (bins >= %0d hits / %0d bins)",
                  coverpoint_op_pct(), MIN_HITS_OP, NUM_OPS);
        $display("  coverpoint a_corner    : %0.1f%% (bins >= %0d hits / %0d bins)",
                  coverpoint_corner_pct(), MIN_HITS_CORNER, NUM_CORNERS);
        $display("  cross op_x_corner      : %0.1f%% (bins >= %0d hit / %0d bins)",
                  cross_op_corner_pct(), MIN_HITS_CROSS, NUM_OPS*NUM_CORNERS);
        $display("  OVERALL (mean)         : %0.1f%%", overall_coverage_pct());
        if (closed)
            $display("  COVERAGE CLOSED after %0d transactions.", closure_txn_count);
        else
            $display("  COVERAGE NOT CLOSED within MAX_TRANSACTIONS=%0d.", MAX_TRANSACTIONS);
        $display("------------------------------------------------------");
        $display("op bin hits    : ADD=%0d SUB=%0d AND=%0d OR=%0d XOR=%0d",
                  op_bin_hits[0], op_bin_hits[1], op_bin_hits[2], op_bin_hits[3], op_bin_hits[4]);
        $display("corner bin hits: ZERO=%0d MAX=%0d MID=%0d",
                  corner_bin_hits[0], corner_bin_hits[1], corner_bin_hits[2]);
        for (int oi = 0; oi < NUM_OPS; oi = oi + 1) begin
            $display("cross row op=%0d: ZERO=%0d MAX=%0d MID=%0d", oi,
                      cross_bin_hits[oi*NUM_CORNERS+0],
                      cross_bin_hits[oi*NUM_CORNERS+1],
                      cross_bin_hits[oi*NUM_CORNERS+2]);
        end

        $finish;
    end

endmodule
