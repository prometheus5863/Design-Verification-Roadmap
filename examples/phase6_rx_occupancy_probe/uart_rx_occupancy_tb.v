`timescale 1ns/1ps
//
// examples/phase6_rx_occupancy_probe/uart_rx_occupancy_tb.v
//
// A CHECK THAT OBSERVES rx_cnt DIRECTLY.
//
// WHY THIS BENCH EXISTS.  2026-11-07 mutation-tested the census's SYNC_ONLY
// classification of STATUS.rx_avail with four mutants, and its control row R4
// came out INDISTINGUISHABLE from its test row R3:
//
//     "Both report the same first failing check with the same byte count,
//      because both make the last byte unreadable -- R3 by stopping the bench
//      asking for it, R4 by stopping the RTL popping it.  The mechanisms
//      differ and this instrument cannot tell them apart ... Separating them
//      needs a check that observes rx_cnt directly; logged, not claimed."
//
// That is the item this bench discharges.  The two mutants differ in kind:
//
//     R3  mutates the STATUS DECODE only.  rx_pop still gates on the true
//         rx_avail, so the DUT's datapath is UNCHANGED and only a reader of
//         STATUS can be misled.                 -> "the sequencing gate lied"
//     R4  mutates the WIRE.  rx_pop gates on it too, so a read of RX_DATA at
//         occupancy 1 does not pop.             -> "the DUT changed"
//
// WHY THE 11-07 BENCH COULD NOT SEPARATE THEM, stated as a mechanism rather
// than as a shortcoming.  That bench takes STATUS.rx_avail as its SEQUENCING
// GATE: it reads RX_DATA only when st[3] is set.  Both mutants clear st[3] at
// occupancy 1, so under both the bench never issues the read that would
// expose the difference.  R4's changed behaviour is real but UNEXERCISED.  No
// amount of checking fixes that, because the distinguishing stimulus is never
// generated.  Separating the two therefore needs BOTH a new observation and a
// new gate, and this bench has both, selectable:
//
//     +gate=0   drain when STATUS says rx_avail  (the 11-07 configuration)
//     +gate=1   drain when the DIRECT PROBE says the FIFO is non-empty
//     +decode=0 no check names rx_avail or st[3] (the 11-07 premise, G2)
//     +decode=1 K5 below checks the decode against the probe
//
// THE PROBE IS WHITE-BOX AND THAT IS DELIBERATE.  dut.rx_cnt is an internal
// register, not a port.  The 11-07 runner's whole adjudication rested on the
// census's premise that no check in the bench names rx_avail, and a bench
// that reaches inside the DUT is a different KIND of bench from one that does
// not -- so the probe is isolated here instead of being bolted onto
// uart_crv_cov_tb.v, whose SYNC_ONLY row it would silently invalidate.
//
// RACE DISCIPLINE.  dut.rx_cnt and dut.rx_wptr are updated at posedge clk.
// Every sample of them in this bench is taken at a NEGEDGE, which is also the
// edge the APB tasks drive on, so no sample races the update that produces it.
// rx_push and rx_pop pulses are deliberately NOT counted: counting a pulse
// from another always block would be exactly such a race.  Occupancy deltas
// carry the same information without one.
//
// Build:
//   iverilog -g2012 -o sim rtl/uart_controller.v \
//       examples/phase6_rx_occupancy_probe/uart_rx_occupancy_tb.v
//   vvp sim +gate=1 +decode=1
//
module uart_rx_occupancy_tb;

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TX   = 4'h3, ADDR_RX     = 4'h4, ADDR_INT   = 4'h5;

    // The RX FIFO depth, as rtl/uart_controller.v decodes rx_full:
    //     wire rx_full = (rx_cnt == 4'd8);
    // Named rather than written as a bare 8, per the 2026-10-11
    // copied-constant defect.
    localparam integer RX_DEPTH = 8;
    localparam integer TX_DEPTH = 8;

    reg        clk = 0, rst_n = 0;
    reg  [3:0] paddr = 0;
    reg  [7:0] pwdata = 0;
    wire [7:0] prdata;
    reg        pwrite = 0, psel = 0, penable = 0;
    wire       pready, tx, irq;
    reg        rx = 1'b1;          // the pin is idle; CTRL[4] routes tx back

    uart_controller dut (
        .clk(clk), .rst_n(rst_n), .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .pready(pready), .tx(tx), .rx(rx), .irq(irq));

    always #5 clk = ~clk;

    // -----------------------------------------------------------------
    // THE PROBE.  Two internal registers, read hierarchically.
    //   occ_live  -- the true RX occupancy, independent of the STATUS decode
    //   wptr_live -- changes iff the RX engine pushed, which is how a push
    //                landing inside a 3-clock APB access is accounted for
    //                EXACTLY rather than argued to be improbable.
    // -----------------------------------------------------------------
    wire [3:0] occ_live  = dut.rx_cnt;
    wire [2:0] wptr_live = dut.rx_wptr;

    integer errors = 0, checks = 0;
    integer gate_probe = 1;    // +gate=1  -> drain on the probe
    integer want_decode = 1;   // +decode=1 -> K5 active
    integer cfg_len = 8, cfg_div = 0, cfg_par = 1, cfg_stop2 = 0;

    // counters for the conservation identity
    integer n_reads = 0;       // RX_DATA accesses issued
    integer n_popped = 0;      // RX_DATA accesses that actually popped

    task check_eq(input [31:0] got, input [31:0] exp, input [8*52:1] what);
        begin
            checks = checks + 1;
            if (got !== exp) begin
                errors = errors + 1;
                $display("  FAIL %0s: got 0x%0h, expected 0x%0h", what, got, exp);
            end
        end
    endtask

    // -----------------------------------------------------------------
    // APB.  One process drives these, so plain tasks are safe.
    // occ_at_read latches the probe at the same negedge that samples
    // prdata, so K5 compares the decode against the occupancy the decode
    // was produced from -- not against a later one.
    // -----------------------------------------------------------------
    reg [7:0] rd_data;
    reg [3:0] occ_at_read;

    task apb_write(input [3:0] a, input [7:0] d);
        begin
            @(negedge clk); psel=1; pwrite=1; paddr=a; pwdata=d; penable=0;
            @(negedge clk); penable=1;
            @(negedge clk); psel=0; penable=0; pwrite=0;
        end
    endtask

    task apb_read(input [3:0] a);
        begin
            @(negedge clk); psel=1; pwrite=0; paddr=a; penable=0;
            @(negedge clk); penable=1; rd_data = prdata; occ_at_read = occ_live;
            @(negedge clk); psel=0; penable=0;
        end
    endtask

    // -----------------------------------------------------------------
    // K2 -- THE POP-EFFECT CHECK.  This is the discriminator.
    //
    // A read of RX_DATA at occupancy >= 1 must remove exactly one entry.
    // The expectation is exact, not statistical: a push inside the access
    // window is detected by wptr moving, so
    //
    //     expected_after = before - 1 + (pushed_during ? 1 : 0)
    //
    // R3 leaves rx_pop alone, so this PASSES under R3 even though STATUS
    // lies.  R4 gates rx_pop on the mutated wire, so a read at occupancy 1
    // pops nothing and this FAILS.  That difference is the whole point.
    // -----------------------------------------------------------------
    reg [3:0] occ_before;
    reg [2:0] wptr_before;
    integer   pushed_during, exp_after;

    task read_rx_checked;
        begin
            @(negedge clk);
            occ_before  = occ_live;
            wptr_before = wptr_live;
            apb_read(ADDR_RX);
            @(negedge clk);
            pushed_during = (wptr_live !== wptr_before) ? 1 : 0;
            n_reads = n_reads + 1;
            if (occ_before != 4'd0) begin
                exp_after = occ_before - 1 + pushed_during;
                check_eq({28'd0, occ_live}, exp_after[31:0],
                         "K2 RX_DATA read popped exactly one entry");
                if (occ_live == (occ_before - 1 + pushed_during))
                    n_popped = n_popped + 1;
            end
        end
    endtask

    // -----------------------------------------------------------------
    // -----------------------------------------------------------------
    // K5 -- the STATUS decode against the probe.
    //
    // WHERE this is sampled is load-bearing, and the first version of this
    // bench got it wrong in a way only a mutant exposed.  K5 was evaluated
    // once per drain-loop pass BEFORE the gate, and under the probe gate the
    // RX FIFO is non-empty for only a few clocks out of every ~176-clock
    // frame, so essentially every evaluation compared 0 against 0.  R1
    // (rx_avail stuck CLEAR) can only be caught at occupancy >= 1, so it
    // ESCAPED a check written precisely to catch it, while R2 (stuck SET) was
    // caught because its failing case is the common one.  A check whose
    // predicate is almost always trivially true is not a weak check, it is an
    // absent one.
    //
    // The repair is an ORDERING, and its sufficiency is exact rather than
    // probable: K5 is now evaluated immediately after the probe reports
    // non-empty, and occupancy can only fall via rx_pop, which only a read of
    // RX_DATA can cause.  No such read is issued between the probe sample and
    // the STATUS read, so occ_at_read >= 1 is guaranteed, not likely.
    // k5_nontrivial counts the evaluations that actually faced a non-empty
    // FIFO, and V4 below refuses to accept the run if that count is zero.
    // -----------------------------------------------------------------
    integer k5_nontrivial = 0;

    task check_decode;
        begin
            apb_read(ADDR_STATUS);
            if (want_decode) begin
                if (occ_at_read != 4'd0) k5_nontrivial = k5_nontrivial + 1;
                check_eq({31'd0, rd_data[3]}, {31'd0, (occ_at_read != 4'd0)},
                         "K5 STATUS.rx_avail agrees with the probe");
            end
        end
    endtask

    reg  [7:0] expq [0:63];
    integer    exp_wr = 0, exp_rd = 0;
    reg  [7:0] byte_to_send;
    integer    pushed, got, guard, guard_limit, k;
    reg        avail_gate;

    task run_burst;
        begin
            // ---- configure with the UART DISABLED so the TX FIFO can fill
            apb_write(ADDR_CTRL, 8'h00);
            apb_write(ADDR_BAUD, cfg_div[7:0]);
            apb_write(ADDR_CTRL, {3'b000, 1'b1, cfg_stop2[0], cfg_par[1:0], 1'b0});

            pushed = 0;
            for (k = 0; k < cfg_len; k = k + 1) begin
                if (pushed < TX_DEPTH) begin
                    byte_to_send = 8'h5A + k[7:0];
                    apb_write(ADDR_TX, byte_to_send);
                    expq[exp_wr % 64] = byte_to_send;
                    exp_wr = exp_wr + 1;
                    pushed = pushed + 1;
                end
            end

            // V1 -- an exactly known value: nothing has been received yet,
            // so the probe must read exactly zero.  A probe that cannot
            // report zero cannot report anything.
            @(negedge clk);
            check_eq({28'd0, occ_live}, 32'd0, "V1 probe reads 0 before enable");

            // ---- enable and drain
            apb_write(ADDR_CTRL, {3'b000, 1'b1, cfg_stop2[0], cfg_par[1:0], 1'b1});

            got = 0;
            guard_limit = (cfg_len + 1) * 16 * (cfg_div + 1) * 13 + 2000;
            guard = 0;
            while (got < pushed && guard < guard_limit) begin
                guard = guard + 1;
                if (gate_probe) begin
                    // probe first, THEN the decode check, so K5 is evaluated
                    // on a FIFO the probe has just said is non-empty
                    @(negedge clk);
                    avail_gate = (occ_live != 4'd0);
                    check_decode;
                end else begin
                    // the 11-07 ordering: STATUS is both the check and the gate
                    check_decode;
                    avail_gate = rd_data[3];
                end
                if (avail_gate) begin
                    read_rx_checked;
                    check_eq({24'd0, rd_data}, {24'd0, expq[exp_rd % 64]},
                             "K6 loopback byte matches reference model");
                    exp_rd = exp_rd + 1;
                    got    = got + 1;
                end
            end

            if (guard >= guard_limit) begin
                errors = errors + 1;
                $display("  FAIL burst watchdog: %0d of %0d bytes returned (par=%0d stop2=%0d div=%0d len=%0d)",
                         got, pushed, cfg_par, cfg_stop2, cfg_div, cfg_len);
            end

            check_eq(exp_wr - exp_rd, 32'd0, "K6b reference queue drained");
        end
    endtask

    initial begin
        if (!$value$plusargs("gate=%d",   gate_probe))  gate_probe  = 1;
        if (!$value$plusargs("decode=%d", want_decode)) want_decode = 1;
        if (!$value$plusargs("len=%d",    cfg_len))     cfg_len     = 8;
        if (!$value$plusargs("div=%d",    cfg_div))     cfg_div     = 0;
        if (!$value$plusargs("par=%d",    cfg_par))     cfg_par     = 1;
        if (!$value$plusargs("stop2=%d",  cfg_stop2))   cfg_stop2   = 0;

        $display("==============================================================");
        $display("RX OCCUPANCY PROBE -- a check that observes rx_cnt directly");
        $display("  gate   : %0s", gate_probe ? "PROBE (dut.rx_cnt != 0)"
                                              : "STATUS (st[3]) -- the 11-07 configuration");
        $display("  decode : %0s", want_decode ? "K5 ACTIVE -- a check names rx_avail"
                                               : "K5 OFF -- the 11-07 premise: no check names rx_avail");
        $display("  config : len=%0d div=%0d par=%0d stop2=%0d",
                 cfg_len, cfg_div, cfg_par, cfg_stop2);
        $display("==============================================================");

        rst_n = 0;
        repeat (4) @(negedge clk);

        // V2 -- an exactly known value under reset.  rtl/uart_controller.v
        // resets rx_cnt to 4'd0 unconditionally, so this is not a plausible
        // range but the only admissible value.
        check_eq({28'd0, occ_live}, 32'd0, "V2 probe reads 0 while in reset");
        rst_n = 1;
        repeat (2) @(negedge clk);
        check_eq({28'd0, occ_live}, 32'd0, "V2b probe reads 0 after reset release");

        run_burst;

        // V3 -- the conservation identity, exact.  Every RX_DATA read issued
        // at occupancy >= 1 must have popped, and a completed drain must
        // leave the FIFO empty.  Both are equalities, not bounds.
        @(negedge clk);
        check_eq({28'd0, occ_live}, 32'd0, "V3 probe reads 0 after a complete drain");
        check_eq(n_popped[31:0], n_reads[31:0], "V3b every issued RX read popped");

        // V4 -- the positive control on K5 itself.  A decode check that never
        // faced a non-empty FIFO has established nothing about the decode,
        // and reporting PASS off the back of it is the 2026-10-22 fault
        // ("coverage closure is a pass criterion, not a report line") in its
        // sharpest form.  Measured, not argued.
        if (want_decode && n_reads > 0)
            check_eq(k5_nontrivial[31:0] >= n_reads[31:0] ? 32'd1 : 32'd0, 32'd1,
                     "V4 K5 was exercised on a non-empty FIFO");

        $display("--------------------------------------------------------------");
        $display("  RX reads issued : %0d", n_reads);
        $display("  reads that popped: %0d", n_popped);
        $display("  bytes returned  : %0d of %0d", got, pushed);
        $display("  K5 non-trivial  : %0d  (evaluations facing a non-empty FIFO)", k5_nontrivial);
        $display("  checks          : %0d", checks);
        $display("  errors          : %0d", errors);
        if (errors == 0) $display("RESULT: PASS");
        else             $display("RESULT: FAIL (%0d errors)", errors);
        $display("--------------------------------------------------------------");
        $finish;
    end

endmodule
