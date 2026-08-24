//------------------------------------------------------------------------
// alu_if_tb.sv
//
// Directed, self-checking testbench for alu_dut, exercising `alu_if`
// (interface + modports), `alu_op_e` (packed enum), and `alu_flags_s`
// (packed struct) from alu_if_and_dut.sv.
//
// CONNECTION NOTE: per TOOLING NOTE (1) in alu_if_and_dut.sv, this
// Icarus 10.3 build cannot accept an interface as a module port, so
// `alu_dut` below is instantiated with a named port map connecting each
// of its plain ports directly to the corresponding field of the `vif`
// interface instance (`.a(vif.a)`, `.result(vif.result)`, etc.) rather
// than passing `vif` as a single port the idiomatic way.
//
// ENUM-IN-TASK/FUNCTION NOTE (found this session, 2026-08-24): this
// Icarus build crashes with an internal compiler assertion
// ("net_scope.cc:211: ... find_enumeration_for_name ... Assertion
// `cur_scope' failed. Aborted") whenever an `alu_op_e`-typed variable is
// *declared* inside a task or function scope -- as a local variable or
// as a port/argument, `automatic` or not. Confirmed with a 6-line
// minimal repro (a task with a single enum-typed argument and no other
// content). Packed-struct-typed locals/arguments in tasks/functions do
// NOT trigger this (also confirmed with a minimal repro), so
// `alu_flags_s` is used freely below in `ref_model`, but every task/
// function below that needs an opcode takes it as a plain
// `logic [2:0]` and casts to `alu_op_e` only in expression context
// (`alu_op_e'(op)`), never as a declared variable -- casts are fine,
// only declarations crash the compiler. This is a real, reproducible
// Icarus 10.3 bug, not a workaround for a syntax restriction; it is
// noted here (rather than silently avoided) so a future session
// retrying on a newer Icarus build knows to simplify this back to plain
// `alu_op_e` locals/arguments once it no longer crashes.
//
// Still deliberately a directed (not constrained-random) testbench with
// plain procedural code (not classes) -- this file's job is data types +
// interfaces specifically. Randomization and OOP testbench components
// (generator/driver/monitor/scoreboard as separate class objects) are
// the next two Phase 2 items per progress.md, and will most naturally
// reuse this same alu_dut as their DUT-under-verification.
//------------------------------------------------------------------------

`timescale 1ns/1ps

module alu_if_tb;

    logic clk = 0;
    logic rst_n;

    always #5 clk = ~clk; // 100 MHz

    // Interface instance: a single typed bundle for every DUT<->TB
    // signal, instead of ten separate wires declared in this module.
    // `vif.op` itself is `alu_op_e`-typed and declared at module
    // (interface) scope, not inside a task/function, so it does not hit
    // the crash described above.
    alu_if vif (.clk(clk), .rst_n(rst_n));

    alu_dut dut (
        .clk          (vif.clk),
        .rst_n        (vif.rst_n),
        .a            (vif.a),
        .b            (vif.b),
        .op           (vif.op),
        .valid        (vif.valid),
        .result       (vif.result),
        .flags        (vif.flags),
        .result_valid (vif.result_valid)
    );

    int errors = 0;
    int checks = 0;

    // .name() on an enum is also not supported in this Icarus build
    // (separately confirmed: "sorry: Enumeration method name() is not
    // currently supported in this context"), so this lookup function
    // stands in for it, purely for readable $display output. Takes the
    // opcode as a raw `logic [2:0]` per the ENUM-IN-TASK/FUNCTION NOTE
    // above -- functions are not exempt from that crash.
    function automatic string op_name(input logic [2:0] op_raw);
        case (op_raw)
            ALU_ADD: op_name = "ALU_ADD";
            ALU_SUB: op_name = "ALU_SUB";
            ALU_AND: op_name = "ALU_AND";
            ALU_OR:  op_name = "ALU_OR";
            ALU_XOR: op_name = "ALU_XOR";
            default: op_name = "ALU_?";
        endcase
    endfunction

    // Independent reference model -- deliberately re-derives expected
    // result/flags from first principles using plain SV arithmetic
    // (not by re-reading the DUT's own code), which is the entire point
    // of a self-checking testbench: it must be able to catch a bug in
    // the DUT's compute logic, so it cannot share that logic. Opcode
    // taken as raw `logic [2:0]` per the ENUM-IN-TASK/FUNCTION NOTE
    // above; `alu_flags_s` (a struct, not an enum) is unaffected and
    // used normally as the output type.
    task automatic ref_model(
        input  logic [7:0] a, b,
        input  logic [2:0] op_raw,
        output logic [7:0] exp_result,
        output alu_flags_s exp_flags
    );
        logic [8:0] add_ext, sub_ext;
        add_ext = {1'b0, a} + {1'b0, b};
        sub_ext = {1'b0, a} - {1'b0, b};

        case (op_raw)
            ALU_ADD: exp_result = add_ext[7:0];
            ALU_SUB: exp_result = sub_ext[7:0];
            ALU_AND: exp_result = a & b;
            ALU_OR:  exp_result = a | b;
            ALU_XOR: exp_result = a ^ b;
            default: exp_result = 8'hxx;
        endcase

        exp_flags.zero  = (exp_result == 8'h00);
        exp_flags.carry = (op_raw == ALU_ADD) ? add_ext[8] :
                           (op_raw == ALU_SUB) ? sub_ext[8] : 1'b0;
        exp_flags.overflow =
            (op_raw == ALU_ADD) ? ((a[7] == b[7]) && (exp_result[7] != a[7])) :
            (op_raw == ALU_SUB) ? ((a[7] != b[7]) && (exp_result[7] != a[7])) :
            1'b0;
    endtask

    // Applies one operation by driving the interface's fields directly
    // (the TB-modport role, even though the modport itself isn't used as
    // a port here -- see the CONNECTION NOTE above), waits for the
    // 1-cycle registered latency, then checks result/flags/result_valid
    // against the reference model. Opcode taken as raw `logic [2:0]` and
    // cast to `alu_op_e'(...)` only in the expression that drives
    // `vif.op` -- per the ENUM-IN-TASK/FUNCTION NOTE above, a cast
    // expression is fine, only a *declared* enum variable/argument
    // inside a task crashes this Icarus build.
    task automatic apply_and_check(input logic [7:0] a, b, input logic [2:0] op_raw);
        logic [7:0] exp_result;
        alu_flags_s exp_flags;

        vif.a     <= a;
        vif.b     <= b;
        vif.op    <= op_raw; // implicit logic[2:0] -> alu_op_e; explicit cast
                                     // (alu_op_e'(...)) is "not yet supported" as a
                                     // cast expression on this Icarus build
        vif.valid <= 1'b1;
        @(posedge clk);
        vif.valid <= 1'b0;
        @(posedge clk); // wait for the registered output to update

        ref_model(a, b, op_raw, exp_result, exp_flags);

        checks++;
        if (vif.result_valid !== 1'b1) begin
            errors++;
            $display("FAIL [op=%s a=%0d b=%0d]: result_valid=%b, expected 1",
                      op_name(op_raw), a, b, vif.result_valid);
        end else if (vif.result !== exp_result) begin
            errors++;
            $display("FAIL [op=%s a=%0d b=%0d]: result=%0d (0x%0h), expected %0d (0x%0h)",
                      op_name(op_raw), a, b, vif.result, vif.result, exp_result, exp_result);
        end else if (vif.flags !== exp_flags) begin
            errors++;
            $display("FAIL [op=%s a=%0d b=%0d]: flags={z,c,ovf}=%b, expected %b",
                      op_name(op_raw), a, b, vif.flags, exp_flags);
        end else begin
            $display("PASS [op=%s a=%0d b=%0d]: result=%0d flags={z,c,ovf}=%b",
                      op_name(op_raw), a, b, vif.result, vif.flags);
        end
    endtask

    initial begin
        $dumpfile("alu_if_wave.vcd");
        $dumpvars(0, alu_if_tb);

        // Reset
        rst_n = 0;
        vif.a = 0; vif.b = 0; vif.op = ALU_ADD; vif.valid = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        // Directed vectors chosen to hit each op at least once, plus
        // known carry/overflow/zero corner cases:
        apply_and_check(8'd10,  8'd20,  ALU_ADD);              // plain add
        apply_and_check(8'hFF,  8'h01,  ALU_ADD);              // carry out, result=0 -> zero+carry
        apply_and_check(8'd127, 8'd1,   ALU_ADD);              // signed overflow (0x7F+1 -> 0x80)
        apply_and_check(8'd5,   8'd5,   ALU_SUB);               // sub -> zero, no borrow
        apply_and_check(8'd0,   8'd1,   ALU_SUB);               // sub -> borrow (carry flag set)
        apply_and_check(8'h80,  8'h01,  ALU_SUB);               // signed overflow on subtract
        apply_and_check(8'hF0,  8'h0F,  ALU_AND);               // AND -> zero
        apply_and_check(8'hAA,  8'h55,  ALU_AND);               // AND -> zero (disjoint bits)
        apply_and_check(8'hF0,  8'h0F,  ALU_OR);                // OR -> all ones
        apply_and_check(8'hAA,  8'h55,  ALU_OR);                // OR -> all ones
        apply_and_check(8'hFF,  8'hFF,  ALU_XOR);               // XOR -> zero
        apply_and_check(8'hAA,  8'h0F,  ALU_XOR);               // XOR -> mixed pattern

        $display("------------------------------------------------------");
        $display("alu_if_tb: %0d checks run, %0d errors", checks, errors);
        if (errors == 0)
            $display("RESULT: ALL CHECKS PASSED");
        else
            $display("RESULT: %0d CHECK(S) FAILED", errors);
        $display("------------------------------------------------------");

        $finish;
    end

endmodule
