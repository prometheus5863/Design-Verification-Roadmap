// examples/phase4_rtl_bringup/uart_controller_tb.v
//
// Directed, self-checking bring-up testbench for rtl/uart_controller.v.
//
// PURPOSE AND SCOPE: this is deliberately NOT the Phase 4 UVM testbench.
// It is the RTL bring-up suite that has to exist before the UVM
// environment can be trusted -- if the DUT itself is broken, a failing
// UVM test tells you nothing about your UVM code. It is plain
// Verilog-2001 so it runs on this repo's Icarus 10.3 build (the
// class-support limitation logged 2026-08-25 does not apply here).
//
// Every check below is a real runtime comparison that increments a
// failure counter and prints the expected/actual values -- not a comment
// asserting that something works. The run ends with a PASS/FAIL summary
// and $fatal on any failure, so a regression cannot pass silently.
//
// Coverage of the verification plan's features (partial by design; the
// constrained-random and coverage-driven parts of the plan belong to the
// UVM environment, not here):
//   T1  reset values                              F1
//   T2  register read/write + RO/WO behaviour     F1, F1.1
//   T3  TX->RX loopback, parity none, 1 stop      F2, F3, F9
//   T4  parity even and odd over loopback         F2, F3, F4
//   T5  two stop bits                             F2, F3
//   T6  TX FIFO fill/full/write-while-full        F5
//   T7  RX FIFO overrun                           F6
//   T8  baud divisor -> measured bit period       F7
//   T9  interrupt masking                         F8
//   T10 corrupted-parity RX frame (negative)      F4
//   T11 framing error (bad stop bit)              F3

`timescale 1ns / 1ps

module uart_controller_tb;

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TX = 4'h3, ADDR_RX = 4'h4, ADDR_INT_EN = 4'h5;

    reg        clk = 0, rst_n = 0;
    reg  [3:0] paddr = 0;
    reg  [7:0] pwdata = 0;
    wire [7:0] prdata;
    reg        pwrite = 0, psel = 0, penable = 0;
    wire       pready, tx, irq;
    reg        rx = 1;

    integer pass_cnt = 0, fail_cnt = 0;
    reg [7:0] rdata;
    integer   i, div_cur;

    uart_controller dut (
        .clk(clk), .rst_n(rst_n), .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .pready(pready), .tx(tx), .rx(rx), .irq(irq)
    );

    always #5 clk = ~clk;   // 100 MHz

    // ---------------- checking helpers ----------------
    task check8(input [511:0] name, input [7:0] got, input [7:0] exp);
    begin
        if (got === exp) begin
            pass_cnt = pass_cnt + 1;
            $display("  PASS  %0s: 0x%02h", name, got);
        end else begin
            fail_cnt = fail_cnt + 1;
            $display("  FAIL  %0s: got 0x%02h expected 0x%02h", name, got, exp);
        end
    end
    endtask

    task check1(input [511:0] name, input got, input exp);
    begin
        if (got === exp) begin
            pass_cnt = pass_cnt + 1;
            $display("  PASS  %0s: %0b", name, got);
        end else begin
            fail_cnt = fail_cnt + 1;
            $display("  FAIL  %0s: got %0b expected %0b", name, got, exp);
        end
    end
    endtask

    task checkint(input [511:0] name, input integer got, input integer exp);
    begin
        if (got === exp) begin
            pass_cnt = pass_cnt + 1;
            $display("  PASS  %0s: %0d", name, got);
        end else begin
            fail_cnt = fail_cnt + 1;
            $display("  FAIL  %0s: got %0d expected %0d", name, got, exp);
        end
    end
    endtask

    // ---------------- APB-lite access ----------------
    task apb_write(input [3:0] a, input [7:0] d);
    begin
        @(negedge clk); psel = 1; pwrite = 1; paddr = a; pwdata = d; penable = 0;
        @(negedge clk); penable = 1;
        @(negedge clk); psel = 0; penable = 0; pwrite = 0;
    end
    endtask

    task apb_read(input [3:0] a, output [7:0] d);
    begin
        @(negedge clk); psel = 1; pwrite = 0; paddr = a; penable = 0;
        @(negedge clk); penable = 1; d = prdata;
        @(negedge clk); psel = 0; penable = 0;
    end
    endtask

    // ---------------- serial bit-level RX driver ----------------
    // Independent of loopback: this is the standalone RX driver the plan's
    // F4 corrupted-parity test requires (plan Section 2.4).
    task ser_send(input [7:0] data, input [1:0] par_mode, input two_stop,
                  input corrupt_par, input bad_stop);
        integer bitper, k;
        reg p;
    begin
        bitper = 16 * (div_cur + 1);
        rx = 0; repeat (bitper) @(posedge clk);            // start
        for (k = 0; k < 8; k = k + 1) begin
            rx = data[k]; repeat (bitper) @(posedge clk);  // LSB first
        end
        if (par_mode != 2'b00) begin
            p = (par_mode == 2'b01) ? ^data : ~^data;
            rx = corrupt_par ? ~p : p;
            repeat (bitper) @(posedge clk);
        end
        rx = bad_stop ? 1'b0 : 1'b1; repeat (bitper) @(posedge clk);
        if (two_stop) begin rx = 1; repeat (bitper) @(posedge clk); end
        rx = 1; repeat (bitper) @(posedge clk);            // idle
    end
    endtask

    // Wait a deterministic number of bit periods.
    //
    // WHY NOT POLL STATUS: the sticky error bits are read-to-clear (see
    // the IMPLEMENTATION DECISION comment in the RTL), so a wait loop
    // that polls STATUS destroys exactly the frame_err/parity_err/
    // overrun_err evidence the test is about to check. That is not a
    // hypothetical: an earlier version of this testbench used a
    // STATUS-polling wait, and a deliberately mutated RTL with broken
    // odd-parity generation passed all 55 checks, because the poll had
    // already cleared parity_err before the check read it. Frame timing
    // here is fully deterministic (baud divisor is known), so a counted
    // wait is both safe and sufficient. See notes/2026-09-17-*.md.
    task wait_bits(input integer nbits);
        integer c;
    begin
        for (c = 0; c < nbits * 16 * (div_cur + 1); c = c + 1) @(posedge clk);
    end
    endtask

    reg ok;
    integer t_fall, t_next, measured, expected;

    initial begin
        $dumpfile("uart_controller_tb.vcd");
        $dumpvars(0, uart_controller_tb);

        $display("=== uart_controller bring-up regression ===");

        // -------- T1: reset values --------
        $display("T1 reset values (F1)");
        repeat (3) @(posedge clk);
        rst_n = 0; repeat (3) @(posedge clk); rst_n = 1; @(posedge clk);
        apb_read(ADDR_CTRL, rdata);   check8("CTRL after reset",     rdata, 8'h00);
        apb_read(ADDR_BAUD, rdata);   check8("BAUD_DIV after reset", rdata, 8'h00);
        apb_read(ADDR_INT_EN, rdata); check8("INT_EN after reset",   rdata, 8'h00);
        apb_read(ADDR_STATUS, rdata);
        // tx_empty=1 (bit1), everything else 0 -> 0x02
        check8("STATUS after reset (tx_empty only)", rdata, 8'h02);
        check1("irq low after reset", irq, 1'b0);

        // -------- T2: register access, RO/WO behaviour --------
        $display("T2 register access + RO/WO (F1, F1.1)");
        apb_write(ADDR_BAUD, 8'h5A); apb_read(ADDR_BAUD, rdata);
        check8("BAUD_DIV readback", rdata, 8'h5A);
        apb_write(ADDR_INT_EN, 8'hFF); apb_read(ADDR_INT_EN, rdata);
        check8("INT_EN readback masked to 3 bits", rdata, 8'h07);
        apb_write(ADDR_CTRL, 8'hFF); apb_read(ADDR_CTRL, rdata);
        check8("CTRL readback masked to 5 bits", rdata, 8'h1F);
        // Write to read-only STATUS must be ignored with no side effects
        apb_write(ADDR_CTRL, 8'h00);           // disable to settle
        apb_write(ADDR_INT_EN, 8'h00);
        apb_write(ADDR_STATUS, 8'hFF);
        apb_read(ADDR_STATUS, rdata);
        check8("STATUS unaffected by write (RO)", rdata, 8'h02);
        // Read of write-only TX_DATA must return a defined value, not hang
        apb_read(ADDR_TX, rdata);
        check8("TX_DATA read is implementation-defined 0x00", rdata, 8'h00);
        apb_read(4'hF, rdata);
        check8("undefined address reads 0x00 without hang", rdata, 8'h00);

        // -------- T3: loopback, no parity, 1 stop --------
        $display("T3 loopback TX->RX, parity none, 1 stop (F2, F3, F9)");
        div_cur = 0;
        apb_write(ADDR_BAUD, 8'h00);
        apb_write(ADDR_CTRL, 8'h11);           // en=1, loopback_en=1, parity none, 1 stop
        apb_write(ADDR_TX, 8'hA5);
        wait_bits(14);                         // start + 8 data + stop + margin
        // One single STATUS read observes rx_avail AND the error bits
        // together, before the read-to-clear side effect matters.
        apb_read(ADDR_STATUS, rdata);
        check1("rx_avail set after loopback frame", rdata[3], 1'b1);
        check1("no frame_err on clean loopback",    rdata[4], 1'b0);
        check1("no parity_err with parity none",    rdata[5], 1'b0);
        apb_read(ADDR_RX, rdata); check8("loopback byte 0xA5", rdata, 8'hA5);

        // -------- T4: parity even / odd --------
        $display("T4 parity even and odd over loopback (F4)");
        apb_write(ADDR_CTRL, 8'h13);           // en, parity_mode=01 (even), loopback
        apb_write(ADDR_TX, 8'h3C);
        wait_bits(15);                         // + parity bit
        apb_read(ADDR_STATUS, rdata);
        check1("rx_avail set (even parity frame)", rdata[3], 1'b1);
        check1("no parity_err (even)",             rdata[5], 1'b0);
        apb_read(ADDR_RX, rdata); check8("even-parity loopback byte 0x3C", rdata, 8'h3C);

        apb_write(ADDR_CTRL, 8'h15);           // en, parity_mode=10 (odd), loopback
        apb_write(ADDR_TX, 8'h7F);
        wait_bits(15);
        apb_read(ADDR_STATUS, rdata);
        check1("rx_avail set (odd parity frame)", rdata[3], 1'b1);
        check1("no parity_err (odd)",             rdata[5], 1'b0);
        apb_read(ADDR_RX, rdata); check8("odd-parity loopback byte 0x7F", rdata, 8'h7F);

        // -------- T5: two stop bits --------
        $display("T5 two stop bits (F2, F3)");
        apb_write(ADDR_CTRL, 8'h19);           // en, stop_bits=1, loopback, parity none
        apb_write(ADDR_TX, 8'hC3);
        wait_bits(16);
        apb_read(ADDR_STATUS, rdata);
        check1("rx_avail set (2 stop bits)",      rdata[3], 1'b1);
        check1("no frame_err with 2 stop bits",   rdata[4], 1'b0);
        apb_read(ADDR_RX, rdata); check8("two-stop loopback byte 0xC3", rdata, 8'hC3);

        // -------- T6: TX FIFO fill / full / write-while-full --------
        $display("T6 TX FIFO fill, full flag, write-while-full (F5)");
        // Disable the core so the TX engine cannot drain the FIFO while filling.
        apb_write(ADDR_CTRL, 8'h00);
        for (i = 0; i < 8; i = i + 1) apb_write(ADDR_TX, 8'h10 + i[7:0]);
        apb_read(ADDR_STATUS, rdata);
        check1("tx_full after 8 pushes", rdata[0], 1'b1);
        check1("tx_empty deasserted",    rdata[1], 1'b0);
        apb_write(ADDR_TX, 8'hEE);             // 9th write must be dropped, not corrupt
        apb_read(ADDR_STATUS, rdata);
        check1("tx_full still set after write-while-full", rdata[0], 1'b1);
        // Drain through loopback and confirm the original 8 bytes, in order
        apb_write(ADDR_CTRL, 8'h11);           // en + loopback
        for (i = 0; i < 8; i = i + 1) begin
            wait_bits(14);
            apb_read(ADDR_RX, rdata);
            check8("drained TX FIFO byte in order", rdata, 8'h10 + i[7:0]);
        end
        wait_bits(4);
        apb_read(ADDR_STATUS, rdata);
        check1("tx_empty after full drain", rdata[1], 1'b1);

        // -------- T7: RX FIFO overrun --------
        $display("T7 RX FIFO overrun (F6)");
        apb_write(ADDR_CTRL, 8'h00);           // reset engines, clear state
        apb_write(ADDR_CTRL, 8'h11);           // en + loopback
        // Push 9 bytes through loopback without draining RX: the 9th must
        // be dropped with overrun_err set and the first 8 left intact.
        for (i = 0; i < 9; i = i + 1) begin
            apb_write(ADDR_TX, 8'h20 + i[7:0]);
            repeat (16 * 13) @(posedge clk);   // let the frame complete
        end
        apb_read(ADDR_STATUS, rdata);
        check1("rx_full after 8 received bytes", rdata[2], 1'b1);
        check1("overrun_err set by 9th byte",    rdata[6], 1'b1);
        // STATUS read above cleared the sticky bits; contents must be intact
        for (i = 0; i < 8; i = i + 1) begin
            apb_read(ADDR_RX, rdata);
            check8("RX FIFO contents intact after overrun", rdata, 8'h20 + i[7:0]);
        end

        // -------- T8: baud divisor -> measured bit period --------
        $display("T8 baud divisor to measured TX bit period (F7)");
        apb_write(ADDR_CTRL, 8'h00);
        div_cur = 2;
        apb_write(ADDR_BAUD, 8'h02);
        apb_write(ADDR_CTRL, 8'h01);           // en, no loopback, parity none
        apb_write(ADDR_TX, 8'h00);             // start bit then eight 0 bits
        @(negedge tx); t_fall = $time;         // start of start bit
        // 0x00 with no parity: start + 8 zero data bits = 9 low bit periods,
        // so the next rising edge is exactly 9 bit periods after the fall.
        @(posedge tx); t_next = $time;
        measured = (t_next - t_fall) / 9;      // ns per bit
        expected = 16 * (div_cur + 1) * 10;    // 10 ns clk period
        checkint("measured TX bit period (ns)", measured, expected);

        // -------- T9: interrupt masking --------
        $display("T9 interrupt masking (F8)");
        apb_write(ADDR_CTRL, 8'h00);
        apb_write(ADDR_INT_EN, 8'h00);
        apb_read(ADDR_STATUS, rdata);
        check1("tx_empty is true", rdata[1], 1'b1);
        check1("irq deasserted while all sources masked", irq, 1'b0);
        apb_write(ADDR_INT_EN, 8'h01);         // tx_empty_en
        check1("irq asserted once tx_empty unmasked", irq, 1'b1);
        apb_write(ADDR_INT_EN, 8'h00);
        check1("irq deasserted again when re-masked", irq, 1'b0);

        // -------- T10: corrupted parity on a received frame --------
        $display("T10 corrupted-parity RX frame, negative test (F4)");
        div_cur = 0;
        apb_write(ADDR_BAUD, 8'h00);
        apb_write(ADDR_CTRL, 8'h03);           // en, parity even, NO loopback
        rx = 1; repeat (32) @(posedge clk);
        ser_send(8'h5A, 2'b01, 1'b0, 1'b1, 1'b0);   // corrupt the parity bit
        apb_read(ADDR_STATUS, rdata);
        check1("parity_err set on corrupted parity", rdata[5], 1'b1);
        // A deliberately bad parity bit must not suppress the data byte
        check1("byte still queued despite parity error", rdata[3], 1'b1);
        apb_read(ADDR_RX, rdata);
        check8("received byte despite bad parity", rdata, 8'h5A);
        // Same frame with correct parity must NOT flag an error
        ser_send(8'h5A, 2'b01, 1'b0, 1'b0, 1'b0);
        apb_read(ADDR_STATUS, rdata);
        check1("no parity_err on correct parity", rdata[5], 1'b0);
        apb_read(ADDR_RX, rdata); check8("clean parity byte", rdata, 8'h5A);

        // -------- T11: framing error --------
        $display("T11 framing error on bad stop bit (F3)");
        apb_write(ADDR_CTRL, 8'h01);           // en, parity none, no loopback
        rx = 1; repeat (32) @(posedge clk);
        ser_send(8'h33, 2'b00, 1'b0, 1'b0, 1'b1);   // stop bit driven low
        apb_read(ADDR_STATUS, rdata);
        check1("frame_err set on bad stop bit", rdata[4], 1'b1);
        ser_send(8'h33, 2'b00, 1'b0, 1'b0, 1'b0);   // clean frame
        apb_read(ADDR_STATUS, rdata);
        check1("frame_err not set on clean frame", rdata[4], 1'b0);

        // -------- T12: sticky error bits are read-to-clear --------
        // This is the RTL's documented deviation from the plan's "live
        // status" wording; it is checked explicitly here so the
        // behaviour is pinned by a test, not just by a comment.
        $display("T12 sticky error bits clear on STATUS read (RTL deviation)");
        div_cur = 0;
        apb_write(ADDR_CTRL, 8'h01);           // en, parity none, no loopback
        rx = 1; repeat (32) @(posedge clk);
        ser_send(8'h33, 2'b00, 1'b0, 1'b0, 1'b1);   // bad stop -> frame_err
        apb_read(ADDR_STATUS, rdata);
        check1("frame_err set by bad frame",          rdata[4], 1'b1);
        apb_read(ADDR_STATUS, rdata);
        check1("frame_err cleared by previous read",   rdata[4], 1'b0);

        // -------- summary --------
        $display("");
        $display("=== SUMMARY: %0d passed, %0d failed ===", pass_cnt, fail_cnt);
        if (fail_cnt != 0) begin
            $display("REGRESSION FAILED");
            $fatal(1, "uart_controller bring-up regression failed");
        end
        $display("REGRESSION PASSED");
        $finish;
    end

    // Global watchdog: a hung DUT must fail, not run forever.
    initial begin
        #4000000;
        $display("FAIL: global timeout -- DUT or testbench hung");
        $fatal(1, "timeout");
    end

endmodule
