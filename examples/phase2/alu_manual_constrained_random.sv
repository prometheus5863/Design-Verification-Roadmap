//------------------------------------------------------------------------
// alu_manual_constrained_random.sv
//
// Phase 2 example: "Randomization (rand/randc, constraints, randomize(),
// dist)" -- the next progress.md item after OOP testbench components
// (2026-08-25). Reuses alu_dut from alu_if_and_dut.sv unmodified, exactly
// as alu_oop_tb_components.sv already does.
//
// TOOLING FINDING (this session, 2026-08-26, confirmed with minimal
// standalone repros before being treated as established -- see
// notes/2026-08-26-randomization-rand-randc-constraints.md, Section 2,
// for full detail and repro listings): this Icarus Verilog 10.3 build
// has NO constrained-random support at all -- `randomize()` is not
// implemented for any class ("No function named `f.randomize' found in
// this context"), and `constraint`/`inside`/`dist` are all explicitly
// rejected by the parser ("sorry: ... not supported yet"). This is a
// materially bigger gap than the missing SV *pieces* found on
// 2026-08-23/24/25 (those had usable in-language workarounds); native
// constrained-random simply is not present on this build.
//
// This file therefore demonstrates the SAME CONCEPTS (uniform random
// fields, `randc`-like guaranteed-cyclic coverage of a small corner-case
// set, `dist`-like weighted biasing toward an interesting corner) via
// hand-written $urandom_range-based equivalents, clearly documented as a
// workaround, not presented as if it were real constraint solving (see
// notes/2026-08-26-*.md, Section 3, for why this equivalence holds for
// the specific simple constraints used here but would NOT scale to
// correlated multi-field constraints -- exactly why real tools implement
// a solver instead of leaving this to hand-written code).
//
// TWO FURTHER TOOLING GAPS found and worked around while building this
// file (both new today, both confirmed with minimal repros -- see
// notes/2026-08-26-*.md, Section 2a and the two additional findings
// below, not yet in that file's initial gap list but consistent with the
// same investigate-before-committing practice):
//
//   - `Foo f = new();` (inline declare+construct) does not parse on this
//     build; the working form is the two-statement `Foo f; f = new();`
//     already used (by necessity, it turns out) throughout this repo's
//     prior class examples.
//   - Calling a `function void` (or any function whose return value is
//     discarded, i.e. invoked "as a task") from WITHIN another class
//     task/function crashes the elaborator
//     ("assert: elab_expr.cc:1257: failed assertion 0"), even though the
//     identical call works fine from a top-level `initial` block. Only
//     task-calling-task (not function-calling-function-as-statement)
//     is safe inside a class method body.
//   - Unpacked fixed-size arrays (`logic [7:0] vals[0:4];`) as CLASS
//     PROPERTIES are fundamentally broken on this build -- both
//     assigning to an indexed element from within a class method and
//     indexing into one from outside the class crash (two different
//     assertions: a codegen-time `stmt_assign.c` assertion and an
//     elaboration-time `elaborate.cc` assertion respectively). SV queues
//     as class properties are also explicitly rejected
//     ("sorry: SV queues inside classes are not yet supported").
//     Module-level (non-class) unpacked arrays work fine (already used,
//     e.g., for `sync_fifo.v`'s memory array) -- so the randc-like
//     corner-value queue and the dist-like weighted-opcode picker below
//     are implemented as plain MODULE-LEVEL tasks operating on a
//     module-level array, not as class methods/properties. This is a
//     genuine design constraint on this simulator, not a style choice --
//     documented here so a future session doesn't rediscover it from
//     scratch, exactly as this repo's established practice requires.
//------------------------------------------------------------------------

`timescale 1ns/1ps

module alu_manual_constrained_random_tb;

    // ---- Transaction: encapsulates one ALU stimulus item ----
    // Plain `logic [2:0]` for op (not `alu_op_e`), per the established
    // enum-in-class-context workaround already used in alu_oop_tb_components.sv.
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

    // ---- Scoreboard: independent reference model + pass/fail tracking ----
    // Identical structure/logic to alu_oop_tb_components.sv's scoreboard
    // (same DUT, same independent reference model) -- reused unmodified
    // here since today's new content is the *generation* side, not the
    // checking side.
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
                $display("FAIL [txn %0d, %s%s]: result_valid=%b, expected 1",
                          idx, opname, is_corner ? " CORNER" : "", actual_result_valid);
            end else if (actual_result !== exp_result) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s%s]: result=%0d, expected %0d",
                          idx, opname, is_corner ? " CORNER" : "", actual_result, exp_result);
            end else if (actual_flags !== exp_flags) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s%s]: flags={z,c,ovf}=%b, expected %b",
                          idx, opname, is_corner ? " CORNER" : "", actual_flags, exp_flags);
            end else begin
                $display("PASS [txn %0d, %s%s]: a=%0d b=%0d result=%0d flags={z,c,ovf}=%b",
                          idx, opname, is_corner ? " CORNER" : "", a, b, actual_result, actual_flags);
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

    // ---- Manual "randc"-like corner-value picker (module-level, see
    // header note on why this cannot live inside a class on this build) ----
    // Guarantees each of the 5 chosen corner values (0x00, 0xFF, 0x80,
    // 0x7F, 0x01 -- the classic unsigned/signed 8-bit boundary values)
    // appears exactly once per shuffled cycle before any repeats, which
    // is the defining behavior of SystemVerilog's `randc` -- implemented
    // here via a manual Fisher-Yates shuffle + pointer, not rejection
    // sampling, so the "exactly once per cycle" guarantee holds by
    // construction rather than probabilistically.
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

    // ---- Manual "dist"-like weighted opcode picker (module-level) ----
    // Emulates `op_raw dist {ALU_SUB := 3, [ALU_ADD:ALU_XOR] :/ 1}` --
    // ALU_SUB gets 3/7 of the weight (~43%) instead of the 1/5 (20%) a
    // uniform pick would give, biasing generation toward SUB because its
    // borrow/overflow flag logic is the ALU's most bug-prone corner (see
    // notes/2026-08-22-combinational-and-sequential-logic-review.md).
    // Implemented as the standard manual technique for weighted random
    // choice: a cumulative-weight table and a single $urandom_range draw
    // against it.
    task weighted_op_select(output logic [2:0] op_raw);
        int r;
        r = $urandom_range(0, 6);           // 7 = 1(ADD)+3(SUB)+1(AND)+1(OR)+1(XOR)
        if (r < 1)      op_raw = 3'b000;    // ALU_ADD: r=0            (1/7)
        else if (r < 4) op_raw = 3'b001;    // ALU_SUB: r=1,2,3        (3/7)
        else if (r < 5) op_raw = 3'b010;    // ALU_AND: r=4            (1/7)
        else if (r < 6) op_raw = 3'b011;    // ALU_OR:  r=5            (1/7)
        else            op_raw = 3'b100;    // ALU_XOR: r=6            (1/7)
    endtask

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

    localparam int NUM_TRANSACTIONS = 20;   // 20 = 4*5: exactly one full
                                             // corner-queue cycle worth of
                                             // corner draws (one every 4th
                                             // transaction), so the
                                             // histogram at the end can
                                             // show all 5 corners hit
                                             // exactly once.

    initial begin
        alu_transaction t;
        logic [7:0] sent_a, sent_b;
        logic [2:0] sent_op;
        bit         is_corner;
        int         op_hist[0:4];
        int         corner_hits[0:4];
        int         corner_idx;

        $dumpfile("alu_manual_constrained_random_wave.vcd");
        $dumpvars(0, alu_manual_constrained_random_tb);

        corner_vals[0] = 8'h00;
        corner_vals[1] = 8'hFF;
        corner_vals[2] = 8'h80;
        corner_vals[3] = 8'h7F;
        corner_vals[4] = 8'h01;
        corner_ptr = 5;   // force a shuffle before the first draw

        sb = new();

        rst_n = 0; a = 0; b = 0; op_raw = 0; valid = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        for (int i = 0; i < NUM_TRANSACTIONS; i++) begin
            // "Generator" step: manual constrained-random fill (see
            // header note -- no native randomize()/constraint on this
            // build). b is uniform over the full 8-bit range (the
            // trivial case a real solver would also reduce to for an
            // unconstrained field); op_raw is dist-like weighted toward
            // SUB; a is uniform EXCEPT every 4th transaction, where it
            // is drawn from the randc-like corner-value queue instead.
            t = new();
            t.b = $urandom_range(0, 255);
            weighted_op_select(sent_op);
            t.op_raw = sent_op;
            op_hist[sent_op] = op_hist[sent_op] + 1;

            if ((i % 4) == 3) begin
                next_corner_value(sent_a);
                t.a = sent_a;
                is_corner = 1;
                case (sent_a)
                    8'h00: corner_hits[0] = corner_hits[0] + 1;
                    8'hFF: corner_hits[1] = corner_hits[1] + 1;
                    8'h80: corner_hits[2] = corner_hits[2] + 1;
                    8'h7F: corner_hits[3] = corner_hits[3] + 1;
                    8'h01: corner_hits[4] = corner_hits[4] + 1;
                endcase
            end else begin
                sent_a = $urandom_range(0, 255);
                t.a = sent_a;
                is_corner = 0;
            end
            sent_b = t.b;

            // "Driver" step: apply to DUT pins (procedural -- no
            // interface-port support on this build, per
            // alu_if_and_dut.sv's TOOLING NOTE 1).
            a <= sent_a; b <= sent_b; op_raw <= sent_op; valid <= 1'b1;
            @(posedge clk);
            valid <= 1'b0;
            @(posedge clk); // wait for the 1-cycle registered DUT latency

            // "Monitor" + "scoreboard" step.
            sb.check(sent_a, sent_b, sent_op, result, flags, result_valid,
                      i, t.op_name(), is_corner);
        end

        sb.report();
        $display("op_raw histogram: ADD=%0d SUB=%0d AND=%0d OR=%0d XOR=%0d (expect SUB notably above uniform ~%0d/%0d each)",
                  op_hist[0], op_hist[1], op_hist[2], op_hist[3], op_hist[4],
                  NUM_TRANSACTIONS, 5);
        $display("corner-value coverage (5 corners, %0d draws): 0x00=%0d 0xFF=%0d 0x80=%0d 0x7F=%0d 0x01=%0d (expect each exactly 1, one full randc-like cycle)",
                  NUM_TRANSACTIONS/4,
                  corner_hits[0], corner_hits[1], corner_hits[2],
                  corner_hits[3], corner_hits[4]);

        $finish;
    end

endmodule
