// examples/phase4_uvm_milestone/uart_uvm_top.v
//
// Structural top for the Phase 4 UVM environment: the DUT plus the SHARED
// RX pin driver (bfm/uart_rx_pin_bfm.v), with every signal cocotb needs to
// write declared here as a `reg`.
//
// WHY THE ENVIRONMENT NEEDED A WRAPPER AT ALL
// ------------------------------------------
// Until 2026-09-27 this environment's TOPLEVEL was `uart_controller` itself
// and `UartSerialDriver` bit-banged `dut.rx` with
//
//     for _ in range(BIT_CYCLES): await RisingEdge(dut.clk)
//
// -- so the serial driver's timebase WAS the DUT's clock.  Two consequences,
// and the second is the one that mattered:
//
//   * a baud mismatch was inexpressible, so this environment structurally
//     could not do the tolerance work the phase6 benches do;
//   * every frame it had ever driven had its bit edges exactly on DUT clock
//     edges, with zero edge-phase variation, so the receiver's oversampling
//     and mid-bit re-check had never been exercised off-grid here at all --
//     under a 69-check regression at 100% functional coverage, which is
//     2026-09-26 item 8 in one sentence: coverage records what the stimulus
//     reached.
//
// Putting the driver in RTL and having the UVM driver PROGRAM it is the
// alternative to reimplementing an independent timebase in Python.  That
// matters because a Python reimplementation would be a THIRD implementation
// of the pin driver, and the 09-26 item that asked for this work asked for
// it precisely so that a third copy would not exist.  Here the Phase 4
// environment and both phase6 benches drive the same module, from two
// different languages.
//
// The BFM control signals are plain `reg`s in this module, which is what
// makes them writable from cocotb.  `rx` is a wire: nothing outside the BFM
// drives the pin, and the old `dut.rx.value = 1` line in the Python is gone
// because there is no longer a `reg` there to write.

`timescale 1ns / 1ps

module uart_uvm_top;

    // --- DUT-facing signals cocotb writes (clock included: cocotb's
    // Clock() drives dut.clk, so it must be a reg here) ---
    reg         clk     = 1'b0;
    reg         rst_n   = 1'b0;
    reg  [3:0]  paddr   = 4'h0;
    reg  [7:0]  pwdata  = 8'h00;
    reg         pwrite  = 1'b0;
    reg         psel    = 1'b0;
    reg         penable = 1'b0;
    wire [7:0]  prdata;
    wire        pready;
    wire        tx;
    wire        irq;

    // --- the pin, and the BFM that drives it ---
    wire        rx;
    reg         bfm_go        = 1'b0;
    reg  [1:0]  bfm_mode      = 2'd0;
    reg  [7:0]  bfm_data      = 8'h00;
    reg  [1:0]  bfm_par       = 2'b00;
    reg         bfm_two_stop  = 1'b0;
    reg         bfm_bad_stop  = 1'b0;
    reg         bfm_bad_par   = 1'b0;
    // BAUD_DIV = 0 in this environment, so one bit is 16 clock cycles at a
    // 10 ns clock = 160 ns = 160000 ps.  The default is the nominal period,
    // so an unprogrammed BFM behaves exactly like the driver it replaces.
    reg  [31:0] bfm_bit_ps    = 32'd160000;
    reg  [31:0] bfm_phase_ps  = 32'd0;
    reg  [31:0] bfm_glitch_ps = 32'd30000;
    wire        bfm_busy;
    wire [31:0] bfm_done_cnt;

    uart_rx_pin_bfm u_rx_bfm (
        .rx(rx), .go(bfm_go), .busy(bfm_busy), .done_cnt(bfm_done_cnt),
        .mode(bfm_mode), .data(bfm_data), .par(bfm_par),
        .two_stop(bfm_two_stop), .bad_stop(bfm_bad_stop),
        .bad_par(bfm_bad_par), .bit_ps(bfm_bit_ps),
        .phase_ps(bfm_phase_ps), .glitch_ps(bfm_glitch_ps)
    );

    // The DUT is UNMODIFIED, as it has been since the 2026-09-17 bring-up.
    uart_controller u_dut (
        .clk(clk), .rst_n(rst_n),
        .paddr(paddr), .pwdata(pwdata), .prdata(prdata),
        .pwrite(pwrite), .psel(psel), .penable(penable), .pready(pready),
        .tx(tx), .rx(rx), .irq(irq)
    );

endmodule
