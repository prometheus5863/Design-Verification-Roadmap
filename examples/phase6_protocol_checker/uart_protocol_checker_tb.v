// examples/phase6_protocol_checker/uart_protocol_checker_tb.v
//
// Standalone exercise of checkers/uart_protocol_checker.v against the v1
// DUT.  Two things have to be true for the checker to be worth binding into
// anything, and this testbench is built to show both:
//
//   1. ZERO violations on correct RTL.  A checker that fires on a good
//      design is worse than no checker.
//   2. ZERO UNEXERCISED RULES.  A rule that never evaluated is a rule with
//      no evidence either way -- the distinction the 2026-10-28 entry drew
//      about an unexercised DISAGREE arm.  The stimulus below is written
//      backwards from the rule list to put every rule in the evaluated
//      column, and the checker prints the evaluation count per rule so the
//      claim is readable rather than asserted.
//
// Detection power is a separate question and is answered separately, by
// mutate.sh: a defect injected into a COPY of the RTL must make the CHECKER
// fire, and the report names which rule caught it.

`timescale 1ns / 1ps

module uart_protocol_checker_tb;

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TXD  = 4'h3, ADDR_RXD    = 4'h4, ADDR_INTEN = 4'h5;

    localparam PAR_NONE = 2'b00, PAR_EVEN = 2'b01, PAR_ODD = 2'b10;

    reg        clk = 1'b0;
    reg        rst_n = 1'b0;
    reg  [3:0] paddr = 4'h0;
    reg  [7:0] pwdata = 8'h00;
    wire [7:0] prdata;
    reg        pwrite = 1'b0;
    reg        psel = 1'b0;
    reg        penable = 1'b0;
    wire       pready;
    wire       tx;
    reg        rx = 1'b1;
    wire       irq;

    integer pass_cnt = 0, fail_cnt = 0;
    integer chk_viol, chk_unexercised;
    reg [7:0] rd;
    integer   div_cur = 1;
    integer   ph;
    integer   a2_before, a2_after, a5_before, a5_after;

    uart_controller dut (
        .clk(clk), .rst_n(rst_n), .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .pready(pready), .tx(tx), .rx(rx), .irq(irq)
    );

    uart_protocol_checker chk (
        .clk(clk), .rst_n(rst_n), .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .pready(pready), .tx(tx), .rx(rx), .irq(irq)
    );

    always #5 clk = ~clk;   // 100 MHz

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

    // ---------------- APB-lite driver ----------------
    task apb_write(input [3:0] a, input [7:0] d);
    begin
        @(posedge clk); paddr <= a; pwdata <= d; pwrite <= 1'b1; psel <= 1'b1;
        @(posedge clk); penable <= 1'b1;
        @(posedge clk); psel <= 1'b0; penable <= 1'b0; pwrite <= 1'b0;
        @(posedge clk);
    end
    endtask

    task apb_read(input [3:0] a, output [7:0] d);
    begin
        @(posedge clk); paddr <= a; pwrite <= 1'b0; psel <= 1'b1;
        @(posedge clk); penable <= 1'b1;
        @(posedge clk); d = prdata;
        psel <= 1'b0; penable <= 1'b0;
        @(posedge clk);
    end
    endtask

    // ---------------- serial stimulus on rx ----------------
    // bad_parity flips the parity bit; bad_stop drives the first stop bit low.
    task ser_send(input [7:0] data, input [1:0] par_mode, input two_stop,
                  input bad_parity, input bad_stop);
        integer bitper, k;
        reg p;
    begin
        bitper = 16 * (div_cur + 1);
        rx = 1'b0;                      // start
        repeat (bitper) @(posedge clk);
        for (k = 0; k < 8; k = k + 1) begin
            rx = data[k];
            repeat (bitper) @(posedge clk);
        end
        if (par_mode != PAR_NONE) begin
            p = (par_mode == PAR_EVEN) ? ^data : ~(^data);
            rx = bad_parity ? ~p : p;
            repeat (bitper) @(posedge clk);
        end
        rx = bad_stop ? 1'b0 : 1'b1;
        repeat (bitper) @(posedge clk);
        if (two_stop) begin
            rx = 1'b1;
            repeat (bitper) @(posedge clk);
        end
        rx = 1'b1;
    end
    endtask

    task wait_bits(input integer nbits);
        integer c;
    begin
        for (c = 0; c < nbits * 16 * (div_cur + 1); c = c + 1) @(posedge clk);
    end
    endtask

    // ---------------- stimulus ----------------
    initial begin
        $dumpfile("uart_protocol_checker_tb.vcd");
        $dumpvars(0, uart_protocol_checker_tb);

        $display("=============================================================");
        $display(" PROTOCOL CHECKER EXERCISE -- uart_controller v1");
        $display("=============================================================");

        // --- 1. reset, which is what exercises R1/R2 -------------------
        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        $display("");
        $display("-- 1. reset held for 8 cycles (exercises R1, R2)");
        check1("tx idles high in reset", tx, 1'b1);
        check1("irq low in reset", irq, 1'b0);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);

        // --- 2. disabled window, which exercises T1 and I1 ------------
        $display("");
        $display("-- 2. disabled window (exercises T1 tx-high-when-disabled, I1)");
        repeat (40) @(posedge clk);
        check1("tx still high while CTRL.en = 0", tx, 1'b1);
        check1("irq still low while INT_EN = 0", irq, 1'b0);

        // --- 3. unmapped reads, which exercise A4 ---------------------
        $display("");
        $display("-- 3. unmapped register reads (exercises A4)");
        apb_read(4'h6, rd);
        check1("read of 0x6 is zero", rd === 8'h00, 1'b1);
        apb_read(4'hF, rd);
        check1("read of 0xF is zero", rd === 8'h00, 1'b1);

        // --- 4. configure and transmit, no parity, 1 stop ------------
        $display("");
        $display("-- 4. TX frame, no parity, 1 stop (exercises T2, T4, T5, T6)");
        div_cur = 1;
        apb_write(ADDR_BAUD, div_cur[7:0]);
        apb_write(ADDR_CTRL, 8'b0_0_00_1);      // en, no parity, 1 stop
        apb_write(ADDR_TXD, 8'hA5);             // LSB 1, so T6 is measurable
        wait_bits(13);

        // --- 5. transmit with even parity, 2 stop bits --------------
        $display("");
        $display("-- 5. TX frame, even parity, 2 stop (exercises T3)");
        apb_write(ADDR_CTRL, 8'b0_1_01_1);      // en, even parity, 2 stop
        apb_write(ADDR_TXD, 8'h3B);
        wait_bits(15);

        // --- 6. transmit with odd parity ---------------------------
        $display("");
        $display("-- 6. TX frame, odd parity, 1 stop (exercises T3 again)");
        apb_write(ADDR_CTRL, 8'b0_0_10_1);      // en, odd parity, 1 stop
        apb_write(ADDR_TXD, 8'h01);
        wait_bits(13);

        // --- 7. receive a good frame -------------------------------
        $display("");
        $display("-- 7. RX a good frame, odd parity");
        ser_send(8'h5A, PAR_ODD, 1'b0, 1'b0, 1'b0);
        wait_bits(2);
        apb_read(ADDR_RXD, rd);
        check1("received byte is 0x5A", rd === 8'h5A, 1'b1);

        // --- 8. a parity error, then the read-to-clear pair --------
        $display("");
        $display("-- 8. RX with bad parity, then two STATUS reads (exercises S1)");
        ser_send(8'h77, PAR_ODD, 1'b0, 1'b1, 1'b0);
        wait_bits(2);
        apb_read(ADDR_STATUS, rd);
        check1("STATUS.parity_err set after a bad-parity frame", rd[5], 1'b1);
        apb_read(ADDR_STATUS, rd);
        check1("STATUS.parity_err cleared by the read", rd[5], 1'b0);

        // --- 9. a frame error, same pair --------------------------
        $display("");
        $display("-- 9. RX with a low stop bit, then two STATUS reads");
        // The DUT must be in NO-PARITY mode for a no-parity frame.  The first
        // run of this testbench left it in ODD parity from section 6 and the
        // frame's stop bit was consumed as a parity bit, so frame_err was
        // never set and the check failed -- a stimulus bug, in the testbench,
        // not in the DUT or the checker.
        apb_write(ADDR_CTRL, 8'b0_0_00_1);      // en, no parity, 1 stop
        ser_send(8'h2C, PAR_NONE, 1'b0, 1'b0, 1'b1);
        wait_bits(3);
        apb_read(ADDR_STATUS, rd);
        check1("STATUS.frame_err set after a bad stop bit", rd[4], 1'b1);
        apb_read(ADDR_STATUS, rd);
        check1("STATUS.frame_err cleared by the read", rd[4], 1'b0);

        // --- 9b. disable mid-frame, which is what exercises T1 --
        // The first mutation run scored "tx not forced high when disabled" as
        // a CHECKER-MISS with zero TB failures: the defect removes the
        // tx_line <= 1 in the !cfg_en branch, and every earlier disable in
        // this testbench happens with tx already idle high, so the mutant is
        // equivalent to correct RTL under that stimulus.  The gap was in the
        // STIMULUS, not in rule T1.  Disabling while tx is LOW -- i.e. in the
        // middle of a frame -- is what distinguishes them.
        $display("");
        $display("-- 9b. disable mid-frame while tx is low (exercises T1 properly)");
        apb_write(ADDR_CTRL, 8'b0_0_00_1);
        apb_write(ADDR_TXD, 8'hFE);             // LSB 0: tx stays low after start
        wait_bits(1);                           // inside the start/data-0 region
        check1("tx is low mid-frame before the disable", tx, 1'b0);
        apb_write(ADDR_CTRL, 8'h00);            // disable mid-frame
        repeat (8) @(posedge clk);
        check1("tx forced high by the disable", tx, 1'b1);
        repeat (40) @(posedge clk);

        // --- 10. a different divisor, and a PHASE SWEEP ----------
        // The checker header predicts that the start bit can be SHORT by up
        // to one oversample period, because the DUT leaves TX_IDLE the cycle
        // it sees a non-empty FIFO without waiting for a baud tick.  The
        // first run of this testbench never produced a short start bit (min
        // == max == one full bit period in all four frames), which left the
        // lower end of T6's window with no evidence.  The truncation depends
        // on the PHASE of baud_cnt when TX_DATA is written, and the APB
        // driver happened to land on the aligned phase every time.  Sweeping
        // the phase by inserting 0..3 idle cycles before the write at
        // div = 3 covers all four phases of (div+1) = 4.
        $display("");
        $display("-- 10. TX at a second divisor, phase-swept (exercises T6 lower end)");
        apb_write(ADDR_CTRL, 8'h00);            // disable while reprogramming
        div_cur = 3;
        apb_write(ADDR_BAUD, div_cur[7:0]);
        apb_write(ADDR_CTRL, 8'b0_0_00_1);
        for (ph = 0; ph < 4; ph = ph + 1) begin
            repeat (ph) @(posedge clk);
            apb_write(ADDR_TXD, 8'h0F);         // LSB 1, so T6 is measurable
            wait_bits(13);
        end

        // --- the verdict, taken BEFORE the planted control -------
        chk.report(chk_viol, chk_unexercised);
        $display("");
        $display("-- verdict on correct RTL");
        checkint("checker violations on correct RTL", chk_viol, 0);
        checkint("applicable checker rules never evaluated", chk_unexercised, 0);

        // --- 11. planted control for the two N/A rules -----------
        // A2 and A5 cannot be exercised by legal stimulus against a DUT with
        // pready tied high: the access phase is one cycle, so there is no
        // "inside the access phase" for a signal to change in.  A rule that
        // can never evaluate is a rule with no evidence that it CAN fire, so
        // the ability is demonstrated here deliberately, by driving an
        // ILLEGAL extended access phase in which paddr changes.  This is a
        // master-side protocol violation on purpose; it runs last, after the
        // verdict above has been taken, so it cannot flatter that verdict.
        $display("");
        $display("-- 11. planted control: an illegal extended access phase");
        a2_before = chk.rule_viol(1);
        a5_before = chk.rule_viol(4);
        @(posedge clk); paddr <= ADDR_CTRL; pwrite <= 1'b0; psel <= 1'b1;
        @(posedge clk); penable <= 1'b1;
        @(posedge clk); paddr <= ADDR_BAUD;   // illegal: changes mid-access
        @(posedge clk); psel <= 1'b0; penable <= 1'b0;
        @(posedge clk);
        a2_after = chk.rule_viol(1);
        a5_after = chk.rule_viol(4);
        check1("planted control makes A2 fire", (a2_after > a2_before), 1'b1);
        check1("planted control makes A5 fire", (a5_after > a5_before), 1'b1);
        $display("     A2 %0d -> %0d, A5 %0d -> %0d",
                 a2_before, a2_after, a5_before, a5_after);

        $display("");
        $display("=============================================================");
        $display(" TB checks: %0d passed, %0d failed", pass_cnt, fail_cnt);
        $display(" CHECKER_VIOLATIONS=%0d", chk_viol);
        $display(" CHECKER_UNEXERCISED=%0d", chk_unexercised);
        if (fail_cnt == 0 && chk_viol == 0 && chk_unexercised == 0)
            $display(" RESULT=PASS");
        else
            $display(" RESULT=FAIL");
        $display("=============================================================");
        $finish;
    end

    initial begin
        #2000000;
        $display(" RESULT=FAIL (timeout)");
        $finish;
    end

endmodule
