//------------------------------------------------------------------------
// alu_oop_tb_components.sv
//
// Phase 2 example: "OOP testbench components" (transaction, generator,
// scoreboard) -- the next unchecked progress.md item after data types /
// interfaces (2026-08-24). Reuses alu_dut from alu_if_and_dut.sv
// unmodified as the DUT-under-verification, per that file's own header
// note that this was the planned next step.
//
// Standard verification-methodology background (ChipVerify, "SystemVerilog
// OOP for verification"; Sutherland/Spear, *SystemVerilog for Verification*,
// 3rd ed., chs. 9-10 on classes and testbench structure; the same
// generator/driver/monitor/scoreboard decomposition VMM/OVM/UVM all
// inherited): a class-based testbench separates STIMULUS GENERATION
// (a `transaction` object encapsulating one set of DUT inputs, produced
// by a `generator`), DRIVING (applying a transaction's fields to DUT
// pins, cycle-by-cycle), MONITORING (sampling DUT pins back into
// observed values), and CHECKING (an independent `scoreboard` with its
// own reference model, comparing observed vs. expected and tracking
// pass/fail state) as separate objects communicating over some channel
// (classically a `mailbox`, or in UVM an analysis port) -- rather than
// one monolithic directed-testbench task doing all four at once, as
// `alu_if_tb.sv` (2026-08-24) still does.
//
// TOOLING NOTES (found this session, 2026-08-25, against the same
// Icarus Verilog 10.3 build documented in alu_if_and_dut.sv and
// alu_if_tb.sv -- each confirmed with a minimal standalone repro before
// working around it here, and several are new findings beyond the
// 2026-08-24 list, worth knowing before attempting Phase 2's next two
// milestones, randomization and coverage):
//
//   5. `mailbox` is not implemented at all, parameterized or not
//      (`mailbox #(int) mbx;` and plain `mailbox mbx;` both fail to
//      parse). `semaphore` was not tested but is expected to fail the
//      same way, since neither is a user-definable SV class -- both are
//      built-in library classes Icarus 10.3 simply does not provide.
//      Generator -> driver/scoreboard hand-off below therefore cannot
//      use the idiomatic mailbox-based channel; see note 8 for what is
//      used instead.
//   6. A class cannot hold a `virtual <interface>` member at all --
//      `virtual simple_if vif;` as a class property fails to parse
//      ("invalid class item"), confirmed with a 2-line minimal repro
//      independent of note (1) in alu_if_and_dut.sv (interfaces cannot
//      be module ports either, but this is a *separate* failure, inside
//      a class body with no module port involved). This is exactly the
//      mechanism real SV/UVM driver and monitor classes use to reach
//      DUT pins from inside a class, so on this build a driver/monitor
//      literally cannot be written as a class that drives a DUT
//      directly -- not a style choice, a hard tool limitation.
//   7. A class method cannot return a class-handle-typed value
//      (`function trans next_trans(...); ... return t; endfunction`
//      fails to elaborate: "sorry: I do not know how to elaborate
//      r-value as IVL_VT_CLASS"), and a class-handle-typed `input`
//      task/function argument fails the same way. `ref` arguments of
//      any type also fail outright ("sorry: Reference ports not
//      supported yet."). A class-handle-typed `output` argument DOES
//      work correctly, as does a plain-typed (non-class) `output`
//      argument -- confirmed both ways with minimal repros. Net effect:
//      a class handle can only be produced by a task via an `output`
//      argument (or read back from a member field after the call), never
//      passed *in* to another task/function by value.
//   8. Consequence of notes 5-7 together: this example's `generator`
//      hands off transactions via `next_transaction(output alu_transaction
//      t)` (note 7's supported direction), but the transaction's *fields*
//      (not the handle itself) are what get passed onward to the
//      scoreboard's `check()` task, as plain scalar `input` arguments --
//      passing the transaction handle itself into `check()` would hit
//      note 7's `input`-class-handle failure. Likewise, since note 6
//      rules out a class-based driver/monitor entirely, DUT pin-driving
//      and result-sampling remain plain procedural code in the `initial`
//      block below (as in `alu_if_tb.sv`), immediately after each
//      `next_transaction()` call, rather than living in separate driver/
//      monitor class objects -- the transaction/generator/scoreboard
//      split IS implemented as real class objects with persistent state
//      below; only the driver/monitor roles are not, and note 6 explains
//      concretely why virtual interfaces exist as a language feature at
//      all: they are precisely the missing piece this build lacks.
//   9. Storing multiple class handles in a container does not work: a
//      queue of class-handle type (`alu_transaction q[$];` then
//      `q.push_back(t)`) crashes the compiler outright ("internal error:
//      Can't find task push_back in class trans", then an assertion
//      failure), and *both* fixed-size (`trans arr[5]`) and dynamic
//      (`trans darr[]; darr = new[5];`) unpacked arrays of class handles
//      fail elaboration with "Scope index expression is not constant"
//      as soon as a *variable* (not a literal) is used to index them --
//      i.e. Icarus appears to elaborate a class-handle array as if it
//      were a generate-block instance array rather than a run-time
//      variable. A queue of a built-in scalar type (`int q[$];`) works
//      fine (confirmed separately) -- only class-handle element types
//      are affected. This example therefore generates and consumes one
//      transaction at a time (a single reused handle, immediately
//      unpacked into scalars) rather than building a batch of
//      transactions up front, which also sidesteps note 7 for the same
//      reason.
//  10. `n++` (and presumably `n--`) on a class member variable, called
//      from inside a class task/function across multiple separate calls
//      (e.g. once per generated transaction in a loop), silently gives
//      the WRONG accumulated value with no error or warning -- 5 calls
//      to a `bump(); n++;` task left `n` at 1, not 5. The equivalent
//      explicit form `n = n + 1;` inside the same task, called the same
//      way, gives the correct accumulated value every time (confirmed
//      with a minimal isolated repro, both forms in the same file for a
//      direct side-by-side comparison). This is the most dangerous
//      finding of this session precisely because it does not error --
//      a scoreboard pass/fail counter using `errors++` would silently
//      under-report on this build. `checks`/`errors`/`num_generated`
//      below all use the explicit `x = x + 1` form for this reason.
//  11. `checker` cannot be used as a class (or other) identifier name --
//      `class checker; ... endclass` fails to parse as a cascade of
//      confusing downstream syntax errors with no direct "reserved word"
//      message, while renaming to `my_checker` (or, as used below,
//      `alu_scoreboard`) compiles cleanly. Consistent with `checker`
//      being a reserved keyword for the IEEE 1800 `checker` (procedural
//      assertion-checker) construct that this Icarus build's lexer
//      recognizes even though it does not implement `checker` bodies.
//  12. `$sformatf()` is not implemented ("System task/function
//      $sformatf() is not defined by any module"), so `check()` below
//      takes a transaction index and op-name string as two separate
//      arguments for `$display` to format directly, rather than
//      pre-building one tag string with `$sformatf()` the way a real
//      UVM-style `report()` call normally would. Plain string
//      concatenation with `{...}` does work where needed elsewhere.
//
// Net practical takeaway for the rest of Phase 2 (randomization,
// coverage) and Phase 4 (UVM): this Icarus 10.3 build can express
// classes, class methods, member state, and single-handle in/out data
// flow, which is enough to demonstrate the transaction/generator/
// scoreboard *concepts* here -- but it cannot run an actual UVM
// testbench (UVM's base classes lean heavily on virtual interfaces,
// analysis ports built on top of mailbox-like TLM channels, and
// polymorphic containers of component/transaction handles, i.e. notes
// 5, 6, 7, and 9 all at once) or a constrained-random testbench in the
// idiomatic style (`randomize()` itself was separately confirmed
// unsupported this session too -- see notes/2026-08-25-*.md). Phase 4
// and the constrained-random half of Phase 2 will need a different
// simulator (Verilator's class support is more complete for some of
// these constructs but has its own gaps; a student/free-tier commercial
// simulator such as Questa or VCS would be the realistic path for a full
// UVM testbench) -- flagged here rather than discovered mid-Phase-4.
//------------------------------------------------------------------------

`timescale 1ns/1ps

module alu_oop_tb;

    // ---- Transaction: encapsulates one ALU stimulus item ----
    // `op` is deliberately plain `logic [2:0]` (not `alu_op_e`), per
    // alu_if_tb.sv's own established workaround for this Icarus build's
    // separate enum-in-task/function crash (2026-08-24 note) -- and,
    // independently, per note 7 above, an enum-typed field assigned
    // from a local variable or an explicit cast inside a class function
    // also failed here (confirmed, not shown as a numbered note above
    // since it is subsumed by the existing enum workaround already in
    // use elsewhere in this repo).
    class alu_transaction;
        logic [7:0] a, b;
        logic [2:0] op_raw;

        // Manual pseudo-random fill via $urandom_range -- NOT the
        // constrained-random `randomize()` method (confirmed unsupported
        // on this build this session; see notes/2026-08-25-*.md). This
        // is intentionally simple: Phase 2's next progress.md item is
        // constrained randomization specifically, so this transaction
        // class is deliberately left ready to gain `rand` fields and a
        // real `randomize()` call once that milestone is tackled (on
        // whatever simulator ends up supporting it).
        function void randomize_fields();
            a      = $urandom_range(0, 255);
            b      = $urandom_range(0, 255);
            op_raw = $urandom_range(0, 4);
        endfunction

        function string op_name();
            case (op_raw)
                ALU_ADD: op_name = "ALU_ADD";
                ALU_SUB: op_name = "ALU_SUB";
                ALU_AND: op_name = "ALU_AND";
                ALU_OR:  op_name = "ALU_OR";
                ALU_XOR: op_name = "ALU_XOR";
                default: op_name = "ALU_?";
            endcase
        endfunction
    endclass

    // ---- Generator: produces transactions on demand ----
    // Hands a transaction back via an `output` argument (note 7) rather
    // than a return value or a mailbox `put()` (note 5) -- the only
    // direction a class handle reliably crosses a task boundary on this
    // build.
    class alu_generator;
        int num_generated = 0;

        task next_transaction(output alu_transaction t);
            t = new();
            t.randomize_fields();
            num_generated = num_generated + 1;  // NOT num_generated++; see note 10
        endtask
    endclass

    // ---- Scoreboard: independent reference model + pass/fail tracking ----
    // Takes the transaction's *fields* as plain scalar inputs (not the
    // transaction handle -- note 7 rules that out) plus the DUT's
    // sampled outputs, re-derives the expected result/flags itself
    // (never by reading the DUT's own logic, which is the entire point
    // of an independent scoreboard), and maintains its own persistent
    // checks/errors counters as class member state.
    class alu_scoreboard;
        int checks = 0;
        int errors = 0;

        task predict(input logic [7:0] a, b, input logic [2:0] op_raw,
                     output logic [7:0] exp_result, output alu_flags_s exp_flags);
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

        // `tag`/`opname` passed as two separate scalar-ish arguments
        // (int + string) rather than a single pre-built string, because
        // `$sformatf()` is also unimplemented on this Icarus build
        // (confirmed separately this session: "System task/function
        // $sformatf() is not defined by any module") -- string
        // *concatenation* via `{...}` does work (used for `op_name()`
        // is not needed here since `$display` itself can take the
        // pieces directly), so each piece is just passed straight into
        // `$display`'s own format string below instead of being
        // pre-assembled.
        task check(input logic [7:0] a, b, input logic [2:0] op_raw,
                   input logic [7:0] actual_result, input alu_flags_s actual_flags,
                   input logic actual_result_valid, input int idx, input string opname);
            logic [7:0] exp_result;
            alu_flags_s exp_flags;
            predict(a, b, op_raw, exp_result, exp_flags);
            checks = checks + 1;  // NOT checks++; see note 10
            if (actual_result_valid !== 1'b1) begin
                errors = errors + 1;  // NOT errors++; see note 10
                $display("FAIL [txn %0d, %s]: result_valid=%b, expected 1",
                          idx, opname, actual_result_valid);
            end else if (actual_result !== exp_result) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s]: result=%0d (0x%0h), expected %0d (0x%0h)",
                          idx, opname, actual_result, actual_result, exp_result, exp_result);
            end else if (actual_flags !== exp_flags) begin
                errors = errors + 1;
                $display("FAIL [txn %0d, %s]: flags={z,c,ovf}=%b, expected %b",
                          idx, opname, actual_flags, exp_flags);
            end else begin
                $display("PASS [txn %0d, %s]: a=%0d b=%0d result=%0d flags={z,c,ovf}=%b",
                          idx, opname, a, b, actual_result, actual_flags);
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

    logic clk = 0;
    logic rst_n;
    always #5 clk = ~clk; // 100 MHz

    // Plain module-scope signals driving alu_dut directly -- not through
    // `alu_if` (note 6 means a class couldn't hold a virtual handle to
    // it anyway, and alu_if_and_dut.sv's own note (1) already rules out
    // using the interface as a module port on this build), and not
    // through a driver *class* (note 6 again) -- the `initial` block
    // below plays the driver/monitor role directly, exactly as
    // alu_if_tb.sv already does, while the generator/scoreboard above
    // are genuine class objects with real, persistent state.
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

    alu_generator  gen;
    alu_scoreboard sb;

    localparam int NUM_TRANSACTIONS = 12;

    initial begin
        alu_transaction t;
        logic [7:0] sent_a, sent_b;
        logic [2:0] sent_op;

        $dumpfile("alu_oop_tb_wave.vcd");
        $dumpvars(0, alu_oop_tb);

        gen = new();
        sb  = new();

        rst_n = 0; a = 0; b = 0; op_raw = 0; valid = 0;
        repeat (3) @(posedge clk);
        rst_n = 1;
        @(posedge clk);

        for (int i = 0; i < NUM_TRANSACTIONS; i++) begin
            // "Generator" step: get one transaction, unpack its fields
            // to plain scalars immediately (note 9 -- no batching into
            // a container of handles).
            gen.next_transaction(t);
            sent_a = t.a; sent_b = t.b; sent_op = t.op_raw;

            // "Driver" step (procedural, per note 6): apply to DUT pins.
            a <= sent_a; b <= sent_b; op_raw <= sent_op; valid <= 1'b1;
            @(posedge clk);
            valid <= 1'b0;
            @(posedge clk); // wait for the 1-cycle registered DUT latency

            // "Monitor" + "scoreboard" step (procedural sampling, then
            // handed to the real scoreboard *object*): compare DUT
            // outputs against the scoreboard's own independent model.
            // (op_name() re-evaluated here, not read from before the
            // wait states, since `t` itself is still valid for the
            // whole loop iteration -- only its handle can't cross into
            // another task, per note 7.)
            sb.check(sent_a, sent_b, sent_op, result, flags, result_valid, i, t.op_name());
        end

        sb.report();
        $display("alu_generator produced %0d transactions total", gen.num_generated);

        $finish;
    end

endmodule
