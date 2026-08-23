// sync_fifo_directed_tb.v
//
// Directed, self-checking testbench for sync_fifo.v (Phase 1 milestone).
// See notes/2026-08-23-phase1-milestone-sync-fifo.md for the test plan
// this file implements.
//
// Run with Icarus Verilog (see tools/setup_iverilog.sh if iverilog is
// not already installed):
//   iverilog -g2012 -o sim sync_fifo.v sync_fifo_directed_tb.v
//   vvp sim
//   gtkwave sync_fifo_wave.vcd   (waveform dump, for local GTKWave use --
//                                  GTKWave itself is not available in the
//                                  automation sandbox this was authored
//                                  in; the dump is generated and verified
//                                  non-empty as evidence the dump
//                                  mechanism works, per the roadmap
//                                  milestone description)
//
// Self-checking approach: an independent SystemVerilog queue (`logic
// [WIDTH-1:0] ref_model[$]`) tracks expected FIFO contents, driven by
// the exact same push/pop discipline the DUT is specified to implement --
// but implemented with a completely different underlying data structure
// (dynamic queue vs. the DUT's fixed-size circular-buffer-with-wrapping-
// pointers), so the reference model cannot share a pointer-arithmetic
// bug with the DUT.

`timescale 1ns/1ps

module tb_sync_fifo;

    localparam WIDTH      = 8;
    localparam ADDR_WIDTH = 3;
    localparam DEPTH      = (1 << ADDR_WIDTH);

    logic                 clk = 0;
    logic                 rst_n;
    logic                 wr_en;
    logic [WIDTH-1:0]     wr_data;
    logic                 full;
    logic                 rd_en;
    logic [WIDTH-1:0]     rd_data;
    logic                 empty;

    sync_fifo #(.WIDTH(WIDTH), .ADDR_WIDTH(ADDR_WIDTH)) dut (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_data(wr_data), .full(full),
        .rd_en(rd_en), .rd_data(rd_data), .empty(empty)
    );

    always #5 clk = ~clk;   // 10 ns period

    // Independent software reference model (dynamic queue).
    logic [WIDTH-1:0] ref_model[$];

    integer errors = 0;
    integer checks = 0;
    logic [WIDTH-1:0] next_push_value = 8'h01;

    // ---------------------------------------------------------------
    // Directed-stimulus tasks. Each drives exactly one clock cycle of
    // wr_en/rd_en, updates the reference model ONLY when the operation
    // was legal (mirroring exactly what the DUT's pointers are specified
    // to do -- an illegal push/pop must leave both the DUT and the
    // reference model unchanged, or the two would silently desync), and
    // checks status flags (and, for reads, data) against the reference
    // model.
    // ---------------------------------------------------------------

    task automatic check_flags(input string tag);
        logic exp_empty, exp_full;
        begin
            exp_empty = (ref_model.size() == 0);
            exp_full  = (ref_model.size() == DEPTH);
            checks = checks + 1;
            if (empty !== exp_empty) begin
                errors = errors + 1;
                $display("[FAIL][%s] t=%0t: empty=%b, expected %b (ref size=%0d)",
                          tag, $time, empty, exp_empty, ref_model.size());
            end
            checks = checks + 1;
            if (full !== exp_full) begin
                errors = errors + 1;
                $display("[FAIL][%s] t=%0t: full=%b, expected %b (ref size=%0d)",
                          tag, $time, full, exp_full, ref_model.size());
            end
        end
    endtask

    task automatic do_push(input string tag);
        logic [WIDTH-1:0] pushed_value;
        logic              was_full;
        begin
            pushed_value = next_push_value;
            was_full = full;
            wr_data = pushed_value;
            wr_en   = 1'b1;
            rd_en   = 1'b0;
            @(posedge clk);
            #1; // let pointers/flags settle post-edge before sampling
            if (!was_full) begin
                ref_model.push_back(pushed_value);
                next_push_value = next_push_value + 1'b1;
            end
            wr_en = 1'b0;
            check_flags(tag);
        end
    endtask

    task automatic do_pop(input string tag);
        logic [WIDTH-1:0] exp_data;
        logic              was_empty;
        begin
            rd_en = 1'b1;
            wr_en = 1'b0;
            // Sample rd_data (combinational, first-word-fall-through)
            // BEFORE the clock edge that consumes it -- rd_data reflects
            // the CURRENT front-of-queue entry, not the entry after this
            // pop takes effect.
            #1;
            was_empty = empty;
            if (!was_empty) begin
                exp_data = ref_model[0];
                checks = checks + 1;
                if (rd_data !== exp_data) begin
                    errors = errors + 1;
                    $display("[FAIL][%s] t=%0t: rd_data=%0d, expected %0d",
                              tag, $time, rd_data, exp_data);
                end
            end
            @(posedge clk);
            #1;
            if (!was_empty) exp_data = ref_model.pop_front();
            rd_en = 1'b0;
            check_flags(tag);
        end
    endtask

    // Combined push+pop in the SAME cycle (tests that both pointers can
    // advance together without interfering with each other).
    task automatic do_push_and_pop(input string tag);
        logic [WIDTH-1:0] pushed_value;
        logic [WIDTH-1:0] exp_pop_data;
        logic              was_empty, was_full;
        begin
            pushed_value = next_push_value;
            wr_data = pushed_value;
            wr_en   = 1'b1;
            rd_en   = 1'b1;
            #1;
            was_empty = empty;
            was_full  = full;
            if (!was_empty) begin
                exp_pop_data = ref_model[0];
                checks = checks + 1;
                if (rd_data !== exp_pop_data) begin
                    errors = errors + 1;
                    $display("[FAIL][%s] t=%0t: rd_data=%0d, expected %0d",
                              tag, $time, rd_data, exp_pop_data);
                end
            end
            @(posedge clk);
            #1;
            if (!was_full)  begin
                ref_model.push_back(pushed_value);
                next_push_value = next_push_value + 1'b1;
            end
            if (!was_empty) exp_pop_data = ref_model.pop_front();
            wr_en = 1'b0;
            rd_en = 1'b0;
            check_flags(tag);
        end
    endtask

    initial begin
        $dumpfile("sync_fifo_wave.vcd");
        $dumpvars(0, tb_sync_fifo);

        wr_en = 0; rd_en = 0; wr_data = '0;
        rst_n = 0;
        repeat (2) @(posedge clk);
        #1;

        // --- Test 1: reset state ---
        check_flags("reset");

        rst_n = 1;
        @(posedge clk);
        #1;
        check_flags("post-reset-release");

        // --- Test 2: fill to full ---
        for (int i = 0; i < DEPTH; i++) do_push("fill-to-full");

        // --- Test 3: illegal push while full (protocol violation --
        // expect an $error from the DUT's assertion in the sim log;
        // reference model correctly does NOT record this push since
        // do_push only advances it when the pointer wasn't already full) ---
        do_push("illegal-push-while-full");

        // --- Test 4: drain to empty, checking FIFO ordering ---
        for (int i = 0; i < DEPTH; i++) do_pop("drain-to-empty");

        // --- Test 5: illegal pop while empty (protocol violation) ---
        do_pop("illegal-pop-while-empty");

        // --- Test 6: wrap-around stress -- push 5, pop 3, push 6 more
        // (crosses the 8-entry pointer wrap boundary), then drain fully,
        // checking ordering throughout ---
        for (int i = 0; i < 5; i++) do_push("wrap-fill-1");
        for (int i = 0; i < 3; i++) do_pop("wrap-drain-1");
        for (int i = 0; i < 6; i++) do_push("wrap-fill-2");
        while (ref_model.size() > 0) do_pop("wrap-drain-2");

        // --- Test 7: simultaneous push+pop across several cycles,
        // starting from empty (first push must land while empty, then
        // steady-state push+pop) ---
        do_push("simul-seed");
        for (int i = 0; i < 10; i++) do_push_and_pop("simul-push-pop");
        do_pop("simul-drain-last");

        $display("---------------------------------------------------------");
        $display("Total checks = %0d, errors = %0d", checks, errors);
        if (errors == 0)
            $display("PASS: sync_fifo matched the reference model on every checked cycle across all 7 directed test phases.");
        else
            $display("FAIL: sync_fifo had %0d mismatch(es) against the reference model.", errors);

        $finish;
    end

endmodule
