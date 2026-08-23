// sync_fifo.v
//
// Phase 1 milestone: synchronous FIFO design + directed, self-checking
// testbench (see notes/2026-08-23-phase1-milestone-sync-fifo.md).
//
// Single-clock-domain synchronous FIFO, parameterized in data width and
// depth (depth = 2**ADDR_WIDTH). Deliberately single-clock: cross-clock-
// domain (CDC) FIFO design with gray-coded pointers and synchronizers is
// Phase 6 material ("CDC verification basics" in the roadmap README);
// this milestone is scoped to the single-clock case to match where
// Phase 1 sits in the roadmap.
//
// Design technique: full/empty disambiguation via one extra pointer bit.
// wr_ptr and rd_ptr are each (ADDR_WIDTH+1) bits wide. The bottom
// ADDR_WIDTH bits index into the memory array; the extra top bit acts as
// a wrap-count parity bit. This is the standard technique for
// distinguishing "completely full" from "completely empty" without a
// separate counter, and generalizes directly to the gray-coded version
// used in async/CDC FIFOs (a natural Phase 6 extension of this exact
// module):
//   empty  <=> wr_ptr == rd_ptr                       (all bits equal)
//   full   <=> same lower ADDR_WIDTH bits, but the top
//              (wrap) bit differs (wr_ptr has wrapped
//              one more time than rd_ptr)
//
// Read is combinational (data_out reflects mem[rd_ptr] immediately,
// "first-word-fall-through" style) rather than registered, which keeps
// the read-side timing simple for this milestone; a registered-read
// variant (one cycle of read latency, common in higher-throughput
// designs) is a natural follow-up noted in the milestone summary.

`timescale 1ns/1ps

module sync_fifo #(
    parameter WIDTH      = 8,
    parameter ADDR_WIDTH = 3   // depth = 2**ADDR_WIDTH = 8 entries
) (
    input  logic                  clk,
    input  logic                  rst_n,     // synchronous, active-low

    input  logic                  wr_en,
    input  logic [WIDTH-1:0]      wr_data,
    output logic                  full,

    input  logic                  rd_en,
    output logic [WIDTH-1:0]      rd_data,
    output logic                  empty
);

    localparam DEPTH = (1 << ADDR_WIDTH);

    logic [WIDTH-1:0]      mem [0:DEPTH-1];
    logic [ADDR_WIDTH:0]   wr_ptr, rd_ptr;   // extra MSB = wrap bit

    // ---------------------------------------------------------------
    // Status flags (combinational -- pure function of the two pointers)
    // ---------------------------------------------------------------
    assign empty = (wr_ptr == rd_ptr);
    assign full  = (wr_ptr[ADDR_WIDTH-1:0] == rd_ptr[ADDR_WIDTH-1:0]) &&
                   (wr_ptr[ADDR_WIDTH]     != rd_ptr[ADDR_WIDTH]);

    // First-word-fall-through combinational read data.
    assign rd_data = mem[rd_ptr[ADDR_WIDTH-1:0]];

    // ---------------------------------------------------------------
    // Write side. wr_en while full is a protocol violation (dropped,
    // not corrupting the FIFO) -- flagged via an explicit runtime check
    // ($error) rather than silently ignored, so a testbench driving an
    // illegal write-while-full sequence gets a loud signal rather than a
    // quietly-swallowed bug. (SystemVerilog immediate `assert (...) else
    // $error(...)` would be the more idiomatic way to write this check,
    // but Icarus Verilog 10.3 -- the simulator available in this
    // sandbox, see tools/setup_iverilog.sh -- does not implement
    // immediate assertion statements ["sorry: Simple immediate assertion
    // statements not implemented"], so a plain `if` is used instead; the
    // semantic intent is identical, and this is worth revisiting with
    // `assert` syntax on a simulator with full SVA support.) This
    // mirrors how a real verification environment would treat a DUT-
    // external protocol violation: it is the *testbench's* job not to do
    // this, and the check exists to catch a testbench bug, not to
    // specify DUT recovery behavior.
    // ---------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            wr_ptr <= '0;
        end else begin
            if (wr_en) begin
                // synthesis translate_off
                if (full)
                    $error("sync_fifo: wr_en asserted while full=1 at time %0t -- write dropped, pointer not advanced (protocol violation, not a design feature)", $time);
                // synthesis translate_on
                if (!full) begin
                    mem[wr_ptr[ADDR_WIDTH-1:0]] <= wr_data;
                    wr_ptr <= wr_ptr + 1'b1;
                end
            end
        end
    end

    // ---------------------------------------------------------------
    // Read side. Symmetric treatment: rd_en while empty is a protocol
    // violation, flagged the same way.
    // ---------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            rd_ptr <= '0;
        end else begin
            if (rd_en) begin
                // synthesis translate_off
                if (empty)
                    $error("sync_fifo: rd_en asserted while empty=1 at time %0t -- read ignored, pointer not advanced (protocol violation, not a design feature)", $time);
                // synthesis translate_on
                if (!empty) begin
                    rd_ptr <= rd_ptr + 1'b1;
                end
            end
        end
    end

endmodule
