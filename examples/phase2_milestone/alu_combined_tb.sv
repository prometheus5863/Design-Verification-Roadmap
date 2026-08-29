//------------------------------------------------------------------------
// alu_combined_tb.sv
//
// Phase 2 MILESTONE: "a self-checking, constrained-random SystemVerilog
// testbench (no UVM yet) for a small DUT ... including a scoreboard and a
// functional coverage model with a coverage report" (README.md, Phase 2).
// This is the last unchecked Phase 2 item in progress.md as of
// 2026-08-28, and that day's AUTOMATION_LOG.md entry explicitly
// recommended this integration as the next session's work: "integrating
// the manual-workaround randomization (2026-08-26), functional-coverage
// (2026-08-26 second session), and assertion-style checker (this
// session) into one combined testbench for a single DUT, rather than the
// three separate demonstration files that exist today."
//
// This file does exactly that. It reuses alu_dut (alu_if_and_dut.sv)
// unmodified, and combines, unmodified in substance (only renamed /
// lightly adapted where the three source files' pieces needed to
// coexist in one module), three previously-separate Phase 2 examples:
//   - alu_manual_constrained_random.sv: the transaction class, the
//     dist-like weighted opcode generator, the randc-like corner-value
//     generator.
//   - alu_manual_functional_coverage.sv: the coverpoint/cross bin model
//     and coverage-driven stopping criterion.
//   - alu_sva_checker.sv: the architecturally SEPARATE, independently-
//     formulated assertion-style checker (alu_ref_model), run as a
//     second, independent check on every transaction alongside the
//     scoreboard -- not a replacement for it. Keeping both is
//     deliberate: a real verification environment layers a scoreboard
//     (transaction-level, reference-model-based) with concurrent
//     assertions (signal-level, protocol/invariant-based) *because* they
//     catch different bug classes and a shared blind spot in one is
//     unlikely to be shared by the other -- demonstrated concretely here
//     by using two independently-formulated reference-model
//     implementations (the scoreboard's widened-add/subtract style from
//     alu_manual_*.sv, and the checker's magnitude-comparison style from
//     alu_sva_checker.sv) rather than one model checked twice.
//
// TOOLING: this build has no native `randomize()`/`constraint`
// (2026-08-26), no native `covergroup` (2026-08-26, second session), and
// no native `assert`/`assert property` in either flavor (2026-08-23,
// re-confirmed 2026-08-28) -- see those dates' notes files for the full
// repro-backed findings. All three gaps are why this file's content is
// "the same concepts, hand-implemented" rather than native SV syntax,
// exactly as each source file already documents individually. No NEW
// tooling gaps were found while integrating these three files into one
// module (all constructs used below were already individually verified
// working in their source files) -- integration itself was the only new
// risk, and it compiled/ran cleanly on the first attempt.
//
// Compile/run (see examples/phase2/alu_manual_constrained_random_sim_output_2026-08-26.txt
// for the established two-file compile pattern this follows):
//   iverilog -g2012 -o sim alu_if_and_dut.sv alu_combined_tb.sv && vvp sim
// (alu_if_and_dut.sv is in examples/phase2/, not this directory -- see
// this session's AUTOMATION_LOG.md entry for the exact invocation used.)
//------------------------------------------------------------------------

`timescale 1ns/1ps

module alu_combined_tb;

    // ======================================================================
    // 1. Transaction (from alu_manual_constrained_random.sv, unmodified)
    // ======================================================================
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

    // ======================================================================
    // 2. Scoreboard (from alu_manual_constrained_random.sv, unmodified --
    //    the widened-add/subtract reference-model formulation)
    // ======================================================================
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
                   input logic actual_result_valid, input int idx, input string opname,
                   input bit is_corner);
            logic [7:0] exp_result;
            alu_flags_s exp_flags;
            predict(a, b, op_raw, exp_result, exp_flags);
            checks = checks + 1;
            if (actual_result_valid !== 1'b1) begin
                errors = errors + 1;
                $display("SCOREBOARD FAIL [txn %0d, %s%s]: result_valid=%b, expected 1",
                          idx, opname, is_corner ? " CORNER" : "", actual_result_valid);
            end else if (actual_result !== exp_result) begin
                errors = errors + 1;
                $display("SCOREBOARD FAIL [txn %0d, %s%s]: result=%0d, expected %0d",
                          idx, opname, is_corner ? " CORNER" : "", actual_result, exp_result);
            end else if (actual_flags !== exp_flags) begin
                errors = errors + 1;
                $display("SCOREBOARD FAIL [txn %0d, %s%s]: flags={z,c,ovf}=%b, expected %b",
                          idx, opname, is_corner ? " CORNER" : "", actual_flags, exp_flags);
            end
        endtask

        function void report();
            $display("------------------------------------------------------");
            $display("alu_scoreboard: %0d checks, %0d errors", checks, errors);
            if (errors == 0)
                $display("RESULT: ALL SCOREBOARD CHECKS PASSED");
            else
                $display("RESULT: %0d SCOREBOARD CHECK(S) FAILED", errors);
            $display("------------------------------------------------------");
        endfunction
    endclass

    // ======================================================================
    // 3. Independent assertion-style checker (from alu_sva_checker.sv,
    //    unmodified -- deliberately DIFFERENT arithmetic formulation from
    //    the scoreboard above: magnitude-comparison carry/borrow and a
    //    sign-extended-truncation overflow check, instead of the
    //    scoreboard's widened-add/subtract style, per that file's header
    //    rationale). Module-level counters (not class properties) since
    //    this is called as a free task, matching alu_sva_checker.sv's own
    //    structure (it is not a class there either).
    // ======================================================================
    int assertion_checks_run    = 0;
    int assertion_checks_passed = 0;

    task automatic alu_ref_model_independent(
        input  logic [7:0] a_in, b_in,
        input  logic [2:0] op_raw_in,
        output logic [7:0] exp_result,
        output logic        exp_zero,
        output logic        exp_carry,
        output logic        exp_overflow
    );
        logic signed [15:0] true_wide;
        begin
            case (op_raw_in)
                3'b000: begin // ALU_ADD
                    exp_result = a_in + b_in;
                    exp_carry  = (a_in > (8'hFF - b_in));
                    true_wide  = $signed({{8{a_in[7]}}, a_in}) +
                                 $signed({{8{b_in[7]}}, b_in});
                    exp_overflow = (true_wide !=
                                    $signed({{8{exp_result[7]}}, exp_result}));
                end
                3'b001: begin // ALU_SUB
                    exp_result = a_in - b_in;
                    exp_carry  = (a_in < b_in);
                    true_wide  = $signed({{8{a_in[7]}}, a_in}) -
                                 $signed({{8{b_in[7]}}, b_in});
                    exp_overflow = (true_wide !=
                                    $signed({{8{exp_result[7]}}, exp_result}));
                end
                3'b010: begin exp_result = a_in & b_in; exp_carry = 1'b0; exp_overflow = 1'b0; end // ALU_AND
                3'b011: begin exp_result = a_in | b_in; exp_carry = 1'b0; exp_overflow = 1'b0; end // ALU_OR
                3'b100: begin exp_result = a_in ^ b_in; exp_carry = 1'b0; exp_overflow = 1'b0; end // ALU_XOR
                default: begin exp_result = 8'hxx; exp_carry = 1'bx; exp_overflow = 1'bx; end
            endcase
            exp_zero = (exp_result == 8'h00);
        end
    endtask

    // Checks the DUT's CURRENT registered outputs against the
    // independent model, given the operands that produced them (the
    // caller is responsible for passing the operands from one cycle
    // earlier -- see the driver loop below). `corrupt` deliberately
    // forces a wrong expected value to prove this checker really can
    // fail, mirroring every prior checker example in this repo.
    task automatic assertion_check(
        input logic [7:0] a_val, b_val,
        input logic [2:0] op_raw_val,
        input logic [7:0] actual_result,
        input alu_flags_s actual_flags,
        input string       label,
        input bit          corrupt = 1'b0
    );
        logic [7:0] exp_result, corrupted_result;
        logic        exp_zero, exp_carry, exp_overflow;
        bit          all_ok;
        begin
            alu_ref_model_independent(a_val, b_val, op_raw_val,
                                       exp_result, exp_zero, exp_carry, exp_overflow);
            assertion_checks_run++;
            all_ok = 1'b1;

            if (corrupt) begin
                corrupted_result = ~exp_result;
                if (!(actual_result === corrupted_result)) begin
                    $display("ASSERTION-CHECK EXPECTED-FAIL (deliberate) [%s]: result=%0h did not match deliberately-wrong expected=%0h (real expected was %0h) -- this failure is correct and proves the checker works",
                              label, actual_result, corrupted_result, exp_result);
                    all_ok = 1'b0;
                end
            end else begin
                if (!(actual_result === exp_result)) begin
                    $display("ASSERTION-CHECK FAIL [%s]: result mismatch: dut=%0h expected=%0h",
                              label, actual_result, exp_result);
                    all_ok = 1'b0;
                end
                if (!(actual_flags.zero === exp_zero)) begin
                    $display("ASSERTION-CHECK FAIL [%s]: zero flag mismatch: dut=%0b expected=%0b",
                              label, actual_flags.zero, exp_zero);
                    all_ok = 1'b0;
                end
                if (!(actual_flags.carry === exp_carry)) begin
                    $display("ASSERTION-CHECK FAIL [%s]: carry flag mismatch: dut=%0b expected=%0b",
                              label, actual_flags.carry, exp_carry);
                    all_ok = 1'b0;
                end
                if (!(actual_flags.overflow === exp_overflow)) begin
                    $display("ASSERTION-CHECK FAIL [%s]: overflow flag mismatch: dut=%0b expected=%0b",
                              label, actual_flags.overflow, exp_overflow);
                    all_ok = 1'b0;
                end
                if (all_ok) assertion_checks_passed++;
            end
        end
    endtask

    // ======================================================================
    // 4. Manual constrained-random generators (from
    //    alu_manual_constrained_random.sv, unmodified)
    // ======================================================================
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
        r = $urandom_range(0, 6);           // 7 = 1(ADD)+3(SUB)+1(AND)+1(OR)+1(XOR)
        if (r < 1)      op_raw = 3'b000;
        else if (r < 4) op_raw = 3'b001;
        else if (r < 5) op_raw = 3'b010;
        else if (r < 6) op_raw = 3'b011;
        else            op_raw = 3'b100;
    endtask

    // ======================================================================
    // 5. Manual functional coverage model (from
    //    alu_manual_functional_coverage.sv, unmodified)
    // ======================================================================
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
        op_idx     = op_raw;
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

    function real overall_coverage_pct();
        overall_coverage_pct =
            (coverpoint_op_pct() + coverpoint_corner_pct() + cross_op_corner_pct()) / 3.0;
    endfunction

    // ======================================================================
    // 6. DUT instantiation + combined driver/monitor/scoreboard/coverage/
    //    assertion-checker loop
    // ======================================================================
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

    localparam int MAX_TRANSACTIONS = 4000;

    initial begin
        alu_transaction t;
        logic [7:0] sent_a, sent_b;
        logic [2:0] sent_op;
        bit         is_corner;
        int         txn_count;
        int         closure_txn_count;
        bit         closed;

        $dumpfile("alu_combined_wave.vcd");
        $dumpvars(0, alu_combined_tb);

        corner_vals[0] = 8'h00;
        corner_vals[1] = 8'hFF;
        corner_vals[2] = 8'h80;
        corner_vals[3] = 8'h7F;
        corner_vals[4] = 8'h01;
        corner_ptr = 5;   // force a shuffle before the first draw

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
                // stimulus, same convention as
                // alu_manual_functional_coverage.sv.
            end else begin
                t = new();
                t.b = $urandom_range(0, 255);
                weighted_op_select(sent_op);
                t.op_raw = sent_op;

                if ((txn_count % 4) == 3) begin
                    next_corner_value(sent_a);
                    t.a = sent_a;
                    is_corner = 1;
                end else begin
                    sent_a = $urandom_range(0, 255);
                    t.a = sent_a;
                    is_corner = 0;
                end
                sent_b = t.b;

                // Driver step.
                a <= sent_a; b <= sent_b; op_raw <= sent_op; valid <= 1'b1;
                @(posedge clk);
                valid <= 1'b0;
                @(posedge clk); // wait for the 1-cycle registered DUT latency

                // Monitor + dual checking: scoreboard (widened-arithmetic
                // reference model) AND the independent assertion-style
                // checker (magnitude-comparison reference model) both
                // check the same DUT output, deliberately via two
                // different formulations (see file header).
                sb.check(sent_a, sent_b, sent_op, result, flags, result_valid,
                          txn_count, t.op_name(), is_corner);
                assertion_check(sent_a, sent_b, sent_op, result, flags,
                                 $sformatf("txn %0d %s%s", txn_count, t.op_name(),
                                           is_corner ? " CORNER" : ""));

                // Coverage sampling.
                sample_coverage(sent_op, sent_a);

                if (overall_coverage_pct() >= 100.0) begin
                    closed = 1;
                    closure_txn_count = txn_count + 1;
                end
            end
        end

        // Deliberate expected-fail case for the assertion-style checker,
        // proving it really can fail and not just always pass -- same
        // idiom as alu_sva_checker.sv's final deliberate check. Run
        // against a real DUT transaction so the "actual" side is genuine
        // hardware output, only the checker's OWN expectation is
        // deliberately corrupted.
        begin
            logic [7:0] corrupt_a, corrupt_b;
            logic [2:0] corrupt_op;
            corrupt_a = 8'h10; corrupt_b = 8'h20; corrupt_op = 3'b000; // ADD
            a <= corrupt_a; b <= corrupt_b; op_raw <= corrupt_op; valid <= 1'b1;
            @(posedge clk);
            valid <= 1'b0;
            @(posedge clk);
            assertion_check(corrupt_a, corrupt_b, corrupt_op, result, flags,
                             "deliberate corrupted-expectation check", 1'b1);
        end

        sb.report();
        $display("------------------------------------------------------");
        $display("ASSERTION-STYLE CHECKER REPORT (independent 2nd reference model)");
        $display("  checks run = %0d, passed = %0d, deliberate-fail cases = 1",
                  assertion_checks_run, assertion_checks_passed);
        if (assertion_checks_passed == assertion_checks_run - 1)
            $display("  PASS: all real assertion-checks matched; the one deliberate corrupted-expectation case correctly failed above.");
        else
            $display("  FAIL: unexpected number of passing assertion-checks -- investigate.");
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
        if (sb.errors == 0 && assertion_checks_passed == assertion_checks_run - 1 && closed)
            $display("MILESTONE RESULT: PASS -- scoreboard clean, assertion-style checker clean (deliberate fail case excluded), coverage closed.");
        else
            $display("MILESTONE RESULT: FAIL -- see reports above for which check did not pass.");
        $finish;
    end

endmodule
