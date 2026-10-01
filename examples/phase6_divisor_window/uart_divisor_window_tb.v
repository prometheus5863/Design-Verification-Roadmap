// examples/phase6_divisor_window/uart_divisor_window_tb.v
//
// THE TWO-DIVISOR WINDOW MEASUREMENT, done at six divisors and four edge
// phases -- and the discovery that the question had been asked of the wrong
// window.
//
// WHY THIS FILE EXISTS
// --------------------
// Since 2026-09-27 the top open item in this repository has been "the
// two-divisor 5 bp window measurement".  As of 2026-09-30 it was the only
// thing standing between F7's admissible payload set at 252/256 and the
// hoped-for 254/256: bytes 0x00 and 0x80 are inadmissible as F7 evidence
// because the adaptive observer's per-byte window (555 bp and 625 bp, law
// 1/(2*g_first), measured exhaustively on 2026-09-29) is NARROWER than the
// DUT's measured 8N1 window (slow 675 bp, fast 400 bp, centre +1.38%,
// measured 2026-09-28).  Both of those DUT numbers were taken at
// BAUD_DIV = 0 and only at BAUD_DIV = 0.  The observer's law is pure
// arithmetic over gap counts and cannot depend on the divisor at all.  The
// DUT's window is a clock-granular property, so it can -- and the +0.50%
// centre shift seen between BAUD_DIV 0 and 1 on 2026-09-28 was a TWO-POINT
// observation with no law behind it, which is why that entry filed it as
// unsettled rather than asserting a mechanism.
//
// WHAT IS PRE-REGISTERED, BEFORE THE RUN
// --------------------------------------
// Written here BEFORE the file was first executed, derived from reading
// rtl/uart_controller.v rather than from any measurement, so the run can
// falsify them.  Let one bit be 16*(d+1) clk, d = BAUD_DIV.
//
//   The RX engine enters RX_START on the clk edge at which the registered
//   `rx_sync` is low, and zeroes `rx_os` there.  `rx_os` then advances only
//   on `os_tick`, and `rx_mid = os_tick & (rx_os == 8)` -- so the start bit
//   is sampled on the NINTH os_tick after detection, not the eighth.  That
//   is a structural +1/16 bit of sampling lateness which does NOT scale
//   with the divisor.  On top of it sits a detection latency of rho clk
//   cycles (the synchroniser flop, plus the residue to the next tick of the
//   FREE-RUNNING baud counter, which is never re-phased on a start edge),
//   worth rho/(16*(d+1)) of a bit, which DOES scale.
//
//   Sampling data bit k (k = 0..7, and k = 8 for the stop bit) therefore
//   happens at (k + 1.5 + 1/16 + rho/(16*(d+1))) nominal bit periods after
//   the true falling edge.  Writing p = 1/16 + rho/(16*(d+1)):
//
//     P1  WIDTH IS EXACTLY 1/9 = 1111.1 bp AT EVERY DIVISOR AND PHASE.
//         slow limit = (1/2 + p)/9, fast limit = (1/2 - p)/9 -- the binding
//         constraint either way is the LAST sampled bit that can be wrong
//         (bit 7 fast, the stop bit slow) -- so the sum is 1/9 and p
//         cancels out of it entirely.
//     P2  CENTRE = (slow - fast)/2 = p/9, so the centre is a direct
//         read-out of the sampling lateness and of nothing else.
//     P3  rho, recovered in CLK CYCLES from the measured centre, is a small
//         INTEGER CONSTANT, the same at every divisor.  At BAUD_DIV = 0 the
//         committed centre of +1.38% gives p = 0.125 bit = 2/16, rho = 1.
//     P4  THE CENTRE DOES NOT GO TO ZERO WITH THE DIVISOR: it has a floor
//         of (1/16)/9 = 69.4 bp from the structural ninth-tick term alone.
//         This is the new candidate mechanism the 2026-09-28 entry asked
//         for; `rx_sync` alone is a 1/(d+1) term and cannot make a floor.
//     P5  THEREFORE THE DUT'S SLOW LIMIT HAS A FLOOR OF (1/2 + 1/16)/9
//         = 1/16 = 625 bp, EXACTLY the observer's limit for 0x80 and ABOVE
//         its 555 bp for 0x00, so no divisor can admit either byte.
//
// HOW THE FIRST RUN CAME OUT (2026-10-01), recorded here rather than
// quietly turned into the new pre-registration:
//   P1 CONFIRMED at every divisor and phase measured.
//   P3 FALSIFIED -- the recovered rho is not constant, not an integer, and
//      not even positive; the centre is not monotone in the divisor.
//   P5's ARGUMENT FALSIFIED -- the pair-measured slow limit reaches 570 bp,
//      well below the claimed 625 bp floor.
//   P5's CONCLUSION SURVIVES, for a different reason, found by A4 below:
//      the question has to be asked PER BYTE, and per byte the DUT's window
//      is WIDER than the pair's, not narrower.
//   A2 MISMATCHED the committed 675/400 at zero edge phase and reproduces
//      it EXACTLY at half an oversample tick -- so the committed pair
//      encodes an edge phase that was never a controlled variable.
//
// WHAT IS MEASURED, AND HOW IT IS ANCHORED
// ----------------------------------------
// Pass criterion per frame is the DUT's own register read-out, identical to
// the Phase 4 environment's `_probe`: STATUS.rx_avail set, none of the
// three sticky error bits set, and RX_DATA equal to the byte driven.  The
// limit is the last |eps| at which EVERY trial byte is clean, walking
// outward from zero -- the same definition as `_window` in uart_uvm_tb.py,
// so the two are comparable by construction.
//
// The pin is driven ONLY by bfm/uart_rx_pin_bfm.v, per the 2026-09-27 rule
// that this repository has exactly one UART RX pin driver.
//
// RUN
//   source tools/setup_iverilog.sh      # do NOT pipe it
//   iverilog -g2012 -o sim_divwin \
//       examples/phase6_divisor_window/uart_divisor_window_tb.v \
//       rtl/uart_controller.v bfm/uart_rx_pin_bfm.v
//   vvp sim_divwin

`timescale 1ns / 1ps

module uart_divisor_window_tb;

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TX   = 4'h3, ADDR_RX     = 4'h4, ADDR_INT_EN = 4'h5;

    // STATUS bit positions (rtl/uart_controller.v, status_val)
    localparam ST_TX_FULL = 0, ST_TX_EMPTY = 1, ST_RX_FULL = 2,
               ST_RX_AVAIL = 3, ST_FRAME = 4, ST_PARITY = 5, ST_OVERRUN = 6;

    // One nominal bit at BAUD_DIV=0 is 16 clk = 160 ns = 160000 ps.
    localparam integer BIT_PS_D0 = 160000;

    // The adaptive observer's per-byte limits, law 1/(2*g_first), measured
    // exhaustively over all 256 bytes on 2026-09-29.  Divisor-independent
    // by construction: the law counts gaps, not clock cycles.
    localparam integer OBS_00 = 555;      // 100/(2*9)  -> 5.5556%
    localparam integer OBS_80 = 625;      // 100/(2*8)  -> 6.2500%

    reg        clk = 0, rst_n = 0;
    reg  [3:0] paddr = 0;
    reg  [7:0] pwdata = 0;
    wire [7:0] prdata;
    reg        pwrite = 0, psel = 0, penable = 0;
    wire       pready, tx, irq;

    // ---- BFM wiring: the single RX pin driver in this repository --------
    wire        rx;
    reg         bfm_go = 0;
    wire        bfm_busy;
    wire [31:0] bfm_done_cnt;
    reg  [1:0]  bfm_mode = 2'd0;
    reg  [7:0]  bfm_data = 8'h00;
    reg  [1:0]  bfm_par  = 2'd0;
    reg         bfm_two_stop = 0, bfm_bad_stop = 0, bfm_bad_par = 0;
    reg  [31:0] bfm_bit_ps = BIT_PS_D0;
    reg  [31:0] bfm_phase_ps = 0;
    reg  [31:0] bfm_glitch_ps = 0;

    uart_controller dut (
        .clk(clk), .rst_n(rst_n), .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .pready(pready), .tx(tx), .rx(rx), .irq(irq)
    );

    uart_rx_pin_bfm bfm (
        .rx(rx), .go(bfm_go), .busy(bfm_busy), .done_cnt(bfm_done_cnt),
        .mode(bfm_mode), .data(bfm_data), .par(bfm_par),
        .two_stop(bfm_two_stop), .bad_stop(bfm_bad_stop),
        .bad_par(bfm_bad_par), .bit_ps(bfm_bit_ps),
        .phase_ps(bfm_phase_ps), .glitch_ps(bfm_glitch_ps)
    );

    always #5 clk = ~clk;   // 100 MHz, 10 ns period

    integer pass_cnt = 0, fail_cnt = 0, trial_cnt = 0;
    reg [7:0] st, got;
    reg       t_ok, t_ok2, p_tmp;
    integer   lim;              // task result: measured limit, bp
    integer   i, dsel, qsel, divv;
    integer   slow_bp, fast_bp;
    integer   wmin, wmax, cmin, cmax, s_pair_min, s_pair_max;
    integer   n_pair_wrong;
    real      pbits, rho_clk;

    localparam integer NDIV = 6, NQ = 4;

    integer divtab  [0:NDIV-1];
    integer slow_t  [0:NDIV*NQ-1];
    integer fast_t  [0:NDIV*NQ-1];
    integer slow00  [0:NDIV*NQ-1];
    integer slow80  [0:NDIV*NQ-1];

    localparam integer NB = 13;
    integer bytab   [0:NB-1];
    integer obstab  [0:NB-1];
    integer dutslow [0:NB-1];
    integer n_inadm, n_inadm_single, bsel, gf, span;
    reg [7:0] bb;

    // ---- GOLDEN REGRESSION TABLES (2026-10-01 measurement) --------------
    // These are this run's own measured numbers, committed so that the suite
    // can tell "the window moved" from "the window is still wherever it
    // was".  They are a REGRESSION ANCHOR, not evidence of correctness: they
    // say nothing about whether the DUT is right, only whether it changed.
    // They exist because mutation testing on 2026-10-01 found that three of
    // five injected RTL defects left every other check in this file passing
    // -- the checks above are inequalities, and an inequality survives any
    // mutation that does not cross it.  See the mutation report for which.
    integer gold_slow [0:NDIV*NQ-1];
    integer gold_fast [0:NDIV*NQ-1];
    integer gold_byte [0:NB-1];
    integer n_gold_diff;

    // ---------------- APB-lite -------------------------------------------
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

    task chk(input [1023:0] name, input ok);
    begin
        if (ok) begin pass_cnt = pass_cnt + 1; $display("  [PASS] %0s", name); end
        else    begin fail_cnt = fail_cnt + 1; $display("  [FAIL] %0s", name); end
    end
    endtask

    // ---------------- one frame, one verdict ------------------------------
    // `tb_div` programs the DUT; `drv_div` is the divisor the DRIVEN bit
    // period is computed from.  They are the same everywhere except in the
    // positive control A5, where deliberately disagreeing by one divisor
    // step must destroy the reception -- a measurement that survives a
    // doubled timebase is not measuring the timebase.
    task do_trial(input integer tb_div, input integer drv_div,
                  input [7:0] data, input integer eps_bp,
                  input integer phase_q, output pass);
        real    bp_r;
        integer tick_ps, settle;
    begin
        trial_cnt = trial_cnt + 1;
        // Deterministic start of trial: reset re-phases the baud counter,
        // so the alignment of the frame with the oversample grid is a
        // CONTROLLED variable here rather than an accident of history.
        // A2 below is the reason that matters.
        rst_n = 0;
        repeat (3) @(negedge clk);
        rst_n = 1;
        apb_write(ADDR_BAUD, tb_div[7:0]);
        apb_write(ADDR_CTRL, 8'h01);            // en=1, parity none, 1 stop
        repeat (4) @(negedge clk);

        bp_r    = 1.0 * BIT_PS_D0 * (drv_div + 1) * (1.0 + eps_bp / 10000.0);
        tick_ps = (BIT_PS_D0 * (drv_div + 1)) / 16;

        bfm_mode      = 2'd0;                   // MODE_FRAME
        bfm_data      = data;
        bfm_par       = 2'd0;
        bfm_two_stop  = 0;
        bfm_bad_stop  = 0;
        bfm_bad_par   = 0;
        bfm_bit_ps    = $rtoi(bp_r + 0.5);
        bfm_phase_ps  = (tick_ps * phase_q) / NQ;

        bfm_go = 1;
        wait (bfm_busy === 1'b1);
        bfm_go = 0;
        wait (bfm_busy === 1'b0);

        // let the DUT finish the stop bit and push into the RX FIFO
        settle = 16 * (tb_div + 1) * 3 + 32;
        repeat (settle) @(posedge clk);

        apb_read(ADDR_STATUS, st);
        apb_read(ADDR_RX, got);
        pass = st[ST_RX_AVAIL] && !st[ST_FRAME] && !st[ST_PARITY]
               && !st[ST_OVERRUN] && (got === data);
    end
    endtask

    // ---------------- the limit, exactly as uart_uvm_tb.py defines it -----
    // Last |eps| at which EVERY trial byte is clean, walking outward from 0.
    // `which` selects the trial set: 0 = {0x01,0x80} (the 2026-09-28 pair),
    // 1 = {0x00} alone, 2 = {0x80} alone.
    task measure_limit(input integer tb_div, input integer drv_div,
                       input integer sign, input integer step_bp,
                       input integer max_bp, input integer phase_q,
                       input integer which);
        integer ee;
        reg     ok, p0, p1, allp;
    begin
        lim = -1; ee = 0; ok = 1;
        while (ok && ee <= max_bp) begin
            if (which == 0) begin
                do_trial(tb_div, drv_div, 8'h01, sign * ee, phase_q, p0);
                do_trial(tb_div, drv_div, 8'h80, sign * ee, phase_q, p1);
                allp = p0 && p1;
            end else if (which == 1) begin
                do_trial(tb_div, drv_div, 8'h00, sign * ee, phase_q, p0);
                allp = p0;
            end else begin
                do_trial(tb_div, drv_div, 8'h80, sign * ee, phase_q, p0);
                allp = p0;
            end
            if (allp) begin lim = ee; ee = ee + step_bp; end
            else ok = 0;
        end
    end
    endtask

    // Slow-limit walk for ONE arbitrary byte, coarse grid, high cap.  The
    // single-transition bytes run out to ~6000 bp, so the 5 bp grid used
    // for the window sweep would cost 1200 steps on 0xFF alone.
    task measure_slow_byte(input integer tb_div, input [7:0] data,
                           input integer step_bp, input integer max_bp,
                           input integer phase_q);
        integer ee;
        reg     ok, p0;
    begin
        lim = -1; ee = 0; ok = 1;
        while (ok && ee <= max_bp) begin
            do_trial(tb_div, tb_div, data, ee, phase_q, p0);
            if (p0) begin lim = ee; ee = ee + step_bp; end
            else ok = 0;
        end
    end
    endtask

    // g_first = 1 + ctz(data), the observer's law parameter (2026-09-29).
    // ctz(0) is 8 here, matching that measurement's g_first = 9 for 0x00.
    function integer gfirst(input [7:0] d);
        integer n;
    begin
        n = 0;
        while (n < 8 && d[n] == 1'b0) n = n + 1;
        gfirst = n + 1;
    end
    endfunction

    // The LAST transition in the framed stream [0, d0..d7, 1], as a count of
    // bit periods from the start edge.  This is the DUT's binding span: the
    // slow limit is (1/2 + p) / span, because sampling that bit early reads
    // the previous one and gets a different value.
    function integer lastspan(input [7:0] d);
        integer k, best;
        reg prev, cur;
    begin
        best = 0;
        for (k = 0; k <= 8; k = k + 1) begin
            prev = (k == 0) ? 1'b0 : d[k-1];        // k=0: the start bit
            cur  = (k == 8) ? 1'b1 : d[k];          // k=8: the stop bit
            if (cur !== prev) best = k + 1;
        end
        lastspan = best;
    end
    endfunction

    initial begin : main
        $display("==============================================================================");
        $display("DUT BAUD-TOLERANCE WINDOW vs BAUD_DIV AND EDGE PHASE");
        $display("2026-10-01, rtl/uart_controller.v through the APB register read-out, 8N1");
        $display("==============================================================================");
        $display("clk 10 ns;  one nominal bit = 16*(div+1) clk;  BIT_PS_D0 = %0d ps", BIT_PS_D0);
        $display("limit = last |eps| at which EVERY trial byte is clean, from 0 outward");
        $display("edge phase q/%0d of ONE oversample tick, tick = bit/16", NQ);
        $display("observer per-byte limits (2026-09-29, law 1/(2*g_first)):");
        $display("    0x00 -> %0d bp     0x80 -> %0d bp     (divisor-independent)",
                 OBS_00, OBS_80);
        $display("");

        divtab[0] = 0;  divtab[1] = 1;  divtab[2] = 2;
        divtab[3] = 3;  divtab[4] = 7;  divtab[5] = 15;

        // ------------------------------------------------------------------
        // A1  eps = 0 must be exact at every divisor, for every trial byte.
        //     An exactly-known value: with no baud error at all there is no
        //     mechanism by which any byte can fail, so a failure here is a
        //     broken bench and every number below it would be meaningless.
        // ------------------------------------------------------------------
        $display("A1  eps = 0 is exact at every divisor and phase (4 bytes x 6 div x 4 phases)");
        t_ok = 1;
        for (dsel = 0; dsel < NDIV; dsel = dsel + 1) begin
            divv = divtab[dsel];
            for (qsel = 0; qsel < NQ; qsel = qsel + 1) begin
                do_trial(divv, divv, 8'h01, 0, qsel, p_tmp); if (!p_tmp) t_ok = 0;
                do_trial(divv, divv, 8'h80, 0, qsel, p_tmp); if (!p_tmp) t_ok = 0;
                do_trial(divv, divv, 8'h00, 0, qsel, p_tmp); if (!p_tmp) t_ok = 0;
                do_trial(divv, divv, 8'hFF, 0, qsel, p_tmp); if (!p_tmp) t_ok = 0;
            end
        end
        chk("A1 every byte decodes exactly at eps = 0, 96 cases", t_ok);
        $display("");

        // ------------------------------------------------------------------
        // A2  THE ANCHOR, AND THE FIRST FINDING.  BAUD_DIV = 0, 25 bp grid,
        //     pair {0x01,0x80} -- the committed numbers are slow 675 / fast
        //     400 (uart_uvm_sim_output_2026-09-28.txt, a different bench in
        //     a different language through a UVM register layer).  Measured
        //     here at each of the four edge phases.  Which phases reproduce
        //     the committed pair is reported rather than assumed, because
        //     an anchor that only matches at one value of an uncontrolled
        //     variable is not an anchor -- it is a measurement of that
        //     variable.
        // ------------------------------------------------------------------
        $display("A2  anchor: 25 bp grid, div 0, committed pair is slow 675 / fast 400");
        $display("      phase   slow_bp   fast_bp   matches committed?");
        t_ok  = 0;    // set when SOME phase matches exactly
        t_ok2 = 1;    // cleared when phase 0 does not match
        for (qsel = 0; qsel < NQ; qsel = qsel + 1) begin
            measure_limit(0, 0, +1, 25, 900, qsel, 0); slow_bp = lim;
            measure_limit(0, 0, -1, 25, 900, qsel, 0); fast_bp = lim;
            $display("      %5d   %7d   %7d   %0s", qsel, slow_bp, fast_bp,
                     (slow_bp == 675 && fast_bp == 400) ? "EXACT" : "no");
            if (slow_bp == 675 && fast_bp == 400) t_ok = 1;
            if (qsel == 0 && !(slow_bp == 675 && fast_bp == 400)) t_ok2 = 0;
        end
        chk("A2a the committed 675/400 is reproduced exactly at zero edge phase",
            t_ok2);
        chk("A2b the committed 675/400 is reproduced exactly at SOME edge phase",
            t_ok);
        $display("");

        // ------------------------------------------------------------------
        // A3  the sweep: six divisors x four edge phases, 5 bp grid.
        // ------------------------------------------------------------------
        $display("A3  5 bp grid, trial pair {0x01,0x80}, six divisors x four phases");
        $display("      div   phase   bit/clk   slow_bp   fast_bp   width_bp   centre_bp");
        for (dsel = 0; dsel < NDIV; dsel = dsel + 1) begin
            divv = divtab[dsel];
            for (qsel = 0; qsel < NQ; qsel = qsel + 1) begin
                i = dsel * NQ + qsel;
                measure_limit(divv, divv, +1, 5, 900, qsel, 0); slow_t[i] = lim;
                measure_limit(divv, divv, -1, 5, 700, qsel, 0); fast_t[i] = lim;
                $display("      %3d   %5d   %7d   %7d   %7d   %8d   %9d",
                         divv, qsel, 16 * (divv + 1), slow_t[i], fast_t[i],
                         slow_t[i] + fast_t[i], (slow_t[i] - fast_t[i]) / 2);
            end
        end
        $display("");

        // ------------------------------------------------------------------
        // P1  width is exactly 1/9 = 1111.1 bp, at every divisor and phase.
        //     Each measured limit is the grid FLOOR of a true limit, so the
        //     true width lies in [W, W + 2*step).  The check is that 1111.1
        //     falls in that interval -- measured value beside derived
        //     bound, not an equality between a measurement and a real.
        // ------------------------------------------------------------------
        $display("P1  width brackets 1/9 = 1111.1 bp at every divisor and phase");
        t_ok = 1; wmin = 99999; wmax = -1;
        for (i = 0; i < NDIV*NQ; i = i + 1) begin
            dsel = slow_t[i] + fast_t[i];
            if (dsel < wmin) wmin = dsel;
            if (dsel > wmax) wmax = dsel;
            if (!(dsel <= 1111 && 1111 < dsel + 10)) begin
                t_ok = 0;
                $display("      div %0d phase %0d: width %0d bp, 1111.1 NOT in [%0d,%0d)",
                         divtab[i/NQ], i%NQ, dsel, dsel, dsel + 10);
            end
        end
        $display("      measured width over all 24 cases: min %0d bp, max %0d bp",
                 wmin, wmax);
        chk("P1 true width brackets 1/9 in all 24 divisor-phase cases", t_ok);
        $display("");

        // ------------------------------------------------------------------
        // P1b  THE EXACT IDENTITY.  A lock-once-and-count observer has a
        //      budget of 1/18 EACH WAY (2026-09-28), hence a total width of
        //      1/9 -- the SAME number.  So the two windows are not merely
        //      close (11.00% vs 11.10% as measured on 09-28): they are
        //      equal, and the whole of the containment failure is
        //      DISPLACEMENT.  Checked by requiring that the 2*1/18 bound
        //      lies in the same bracket as the measured DUT width.
        // ------------------------------------------------------------------
        $display("P1b DUT width == 2 x the observer's 1/18 budget == 1/9, exactly");
        t_ok = 1;
        for (i = 0; i < NDIV*NQ; i = i + 1) begin
            dsel = slow_t[i] + fast_t[i];
            if (!(dsel <= 2*555 + 1 && 2*555 + 1 < dsel + 10)) t_ok = 0;
        end
        chk("P1b 2 x 555.56 bp = 1111.1 bp brackets the DUT width in all 24 cases",
            t_ok);
        $display("");

        // ------------------------------------------------------------------
        // P2/P3  recover rho, the detection latency, in CLK CYCLES, from the
        //        measured centre:  centre = p/9,  p = 1/16 + rho/(16(d+1)).
        //        Grid MIDPOINTS are used, since the floor biases each limit
        //        by at most half a step.  P3 claims rho is one small
        //        positive integer for all of them.
        // ------------------------------------------------------------------
        $display("P2/P3  rho recovered from the centre, in clk cycles (phase 0 column)");
        $display("      div   centre_bp(mid)   p(bits)    rho(clk)");
        for (dsel = 0; dsel < NDIV; dsel = dsel + 1) begin
            divv  = divtab[dsel];
            i     = dsel * NQ;
            pbits = ((slow_t[i] - fast_t[i]) / 2.0) / 10000.0 * 9.0;
            rho_clk = (pbits - 1.0 / 16.0) * 16.0 * (divv + 1);
            $display("      %3d   %13.1f   %8.5f   %9.3f",
                     divv, (slow_t[i] - fast_t[i]) / 2.0, pbits, rho_clk);
        end
        t_ok = 1;
        for (dsel = 0; dsel < NDIV; dsel = dsel + 1) begin
            i = dsel * NQ;
            pbits = ((slow_t[i] - fast_t[i]) / 2.0) / 10000.0 * 9.0;
            rho_clk = (pbits - 1.0 / 16.0) * 16.0 * (divtab[dsel] + 1);
            if (rho_clk < 0.0) t_ok = 0;
        end
        chk("P3 the recovered rho is non-negative at every divisor", t_ok);
        $display("      (a negative rho is unphysical: it would be a detection that");
        $display("       happens BEFORE the edge.  P3 is reported, not repaired.)");
        $display("");

        // ------------------------------------------------------------------
        // P5  the claimed 625 bp floor on the PAIR-measured slow limit.
        // ------------------------------------------------------------------
        $display("P5  the claimed floor: pair-measured slow limit >= 625 bp = 1/16");
        s_pair_min = 99999; s_pair_max = -1;
        for (i = 0; i < NDIV*NQ; i = i + 1) begin
            if (slow_t[i] < s_pair_min) s_pair_min = slow_t[i];
            if (slow_t[i] > s_pair_max) s_pair_max = slow_t[i];
        end
        $display("      pair-measured slow limit over 24 cases: min %0d bp, max %0d bp",
                 s_pair_min, s_pair_max);
        chk("P5 pair-measured slow limit >= 625 bp in all 24 cases",
            s_pair_min >= 625);
        $display("");

        // ------------------------------------------------------------------
        // A4  THE ANSWER TO THE TOP ITEM, asked of the right window.
        //
        //     F7 admissibility is a statement about ONE BYTE: can the
        //     observer arbitrate a frame carrying THIS payload?  So the
        //     window that has to be contained is the DUT's window FOR THAT
        //     BYTE, not the DUT window measured over a trial pair.  A pair
        //     window is an INTERSECTION over its bytes and is therefore
        //     never wider than any member -- using it here understates the
        //     DUT and can only ever produce a FALSE "contains" verdict.
        //     0x80 is the case that matters: its bit 7 is 1, so a stop
        //     sample that falls past the end of the stop bit reads the idle
        //     line as a valid stop and the byte survives further than 0x01
        //     does.  Both verdicts are computed below and counted against
        //     each other.
        // ------------------------------------------------------------------
        $display("A4  per-byte DUT slow limit vs the observer, six divisors x four phases");
        $display("      div   phase   slow(0x00)   obs 555      slow(0x80)   obs 625");
        n_pair_wrong = 0;
        for (dsel = 0; dsel < NDIV; dsel = dsel + 1) begin
            divv = divtab[dsel];
            for (qsel = 0; qsel < NQ; qsel = qsel + 1) begin
                i = dsel * NQ + qsel;
                measure_limit(divv, divv, +1, 5, 900, qsel, 1); slow00[i] = lim;
                measure_limit(divv, divv, +1, 5, 900, qsel, 2); slow80[i] = lim;
                $display("      %3d   %5d   %10d   %10s   %10d   %10s",
                         divv, qsel, slow00[i],
                         (OBS_00 >= slow00[i]) ? "contains" : "NARROWER",
                         slow80[i],
                         (OBS_80 >= slow80[i]) ? "contains" : "NARROWER");
                // the pair-based verdict for 0x80, and whether it is wrong
                if ((OBS_80 >= slow_t[i]) && !(OBS_80 >= slow80[i]))
                    n_pair_wrong = n_pair_wrong + 1;
            end
        end
        t_ok = 1;
        for (i = 0; i < NDIV*NQ; i = i + 1) begin
            if (OBS_00 >= slow00[i]) t_ok = 0;
            if (OBS_80 >= slow80[i]) t_ok = 0;
        end
        chk("A4 no divisor or phase makes 0x00 or 0x80 admissible: 252/256 stands",
            t_ok);
        $display("      cases where the PAIR window says 0x80 is contained and the");
        $display("      per-byte window says it is not: %0d of %0d",
                 n_pair_wrong, NDIV*NQ);
        chk("A4b the pair-based window produces at least one wrong verdict",
            n_pair_wrong > 0);
        $display("");

        // ------------------------------------------------------------------
        // A5  POSITIVE CONTROL ON THE MEASUREMENT ITSELF (2026-09-29 rule:
        //     a mutation that does not arrive is indistinguishable from a
        //     system that does not respond).  Drive the frame with the bit
        //     period of the NEXT divisor up while the DUT is programmed for
        //     this one -- a 100% timebase error.  Reception at eps = 0 must
        //     FAIL.  Without this, every zero above could be the bench not
        //     driving the pin at all.
        // ------------------------------------------------------------------
        $display("A5  positive control: a driven timebase from the wrong divisor");
        do_trial(0, 1, 8'h01, 0, 0, t_ok);
        $display("      div 0 programmed, driven at div 1 bit period: %0s",
                 t_ok ? "RECEIVED (bad)" : "rejected");
        chk("A5 a 2x timebase error is detected by the trial mechanism", !t_ok);
        do_trial(1, 0, 8'h01, 0, 0, t_ok);
        $display("      div 1 programmed, driven at div 0 bit period: %0s",
                 t_ok ? "RECEIVED (bad)" : "rejected");
        chk("A5b the control fires in both directions", !t_ok);
        $display("");

        // ------------------------------------------------------------------
        // A6  the phase spread, stated as a number.  If the centre moves
        //     with the edge phase at all, then any single-phase window
        //     measurement -- including the committed one -- is a sample of
        //     a distribution and not a property of the DUT.
        // ------------------------------------------------------------------
        $display("A6  how much of the window position is edge phase, per divisor");
        $display("      div   centre min   centre max   spread_bp");
        t_ok = 0;
        for (dsel = 0; dsel < NDIV; dsel = dsel + 1) begin
            cmin = 99999; cmax = -99999;
            for (qsel = 0; qsel < NQ; qsel = qsel + 1) begin
                i = dsel * NQ + qsel;
                if ((slow_t[i] - fast_t[i]) / 2 < cmin) cmin = (slow_t[i] - fast_t[i]) / 2;
                if ((slow_t[i] - fast_t[i]) / 2 > cmax) cmax = (slow_t[i] - fast_t[i]) / 2;
            end
            $display("      %3d   %10d   %10d   %9d",
                     divtab[dsel], cmin, cmax, cmax - cmin);
            if (cmax - cmin > 0) t_ok = 1;
        end
        chk("A6 the window centre depends on the edge phase at some divisor",
            t_ok);
        $display("");

        // ------------------------------------------------------------------
        // A7  THE CONSEQUENCE, AND IT IS NOT A SMALL ONE.
        //
        //     A4 shows the pair window understates the DUT per byte.  The
        //     2026-09-29 V4 containment check compared EVERY byte's observer
        //     limit against that ONE pair-derived DUT window (slow 675 bp),
        //     so it can only have been right for the bytes whose own DUT
        //     limit happens to equal the pair's.  Asked per byte the
        //     arithmetic is:
        //
        //       observer limit  = (1/2) / g_first,   g_first = 1 + ctz(b)
        //                         (position of the FIRST transition)
        //       DUT slow limit  = (1/2 + p) / span,  span = position of the
        //                         LAST transition in [0, d0..d7, 1]
        //
        //     Containment needs span/g_first >= 1 + 2p.  Since the framed
        //     stream begins at 0 and ends at 1, span >= g_first always, with
        //     EQUALITY exactly when the stream has a single transition --
        //     and then containment needs p <= 0, which no real receiver can
        //     give.  There are NINE such bytes: 0x00, 0x80, 0xC0, 0xE0,
        //     0xF0, 0xF8, 0xFC, 0xFE, 0xFF.  Every one of them should be
        //     inadmissible, not two.
        //
        //     Measured below per byte, against the observer's own law, with
        //     four multi-transition bytes as controls that must remain
        //     admissible.  0x40 is included deliberately: it has the largest
        //     g_first of any multi-transition byte (7), so it is the next
        //     byte to fall if p ever exceeds 1/7.
        // ------------------------------------------------------------------
        $display("A7  per-byte containment under the observer's OWN law, div 0, phase 0");
        $display("      byte   g_first   span   obs_bp   DUT_slow_bp   verdict");
        bytab[0]  = 8'h00; bytab[1]  = 8'h80; bytab[2]  = 8'hC0;
        bytab[3]  = 8'hE0; bytab[4]  = 8'hF0; bytab[5]  = 8'hF8;
        bytab[6]  = 8'hFC; bytab[7]  = 8'hFE; bytab[8]  = 8'hFF;
        bytab[9]  = 8'h40; bytab[10] = 8'h55; bytab[11] = 8'hAA;
        bytab[12] = 8'h01;
        n_inadm = 0; n_inadm_single = 0;
        for (bsel = 0; bsel < NB; bsel = bsel + 1) begin
            bb    = bytab[bsel][7:0];
            gf    = gfirst(bb);
            span  = lastspan(bb);
            obstab[bsel] = 10000 / (2 * gf);
            measure_slow_byte(0, bb, 25, 6000, 0);
            dutslow[bsel] = lim;
            $display("      0x%02h   %7d   %4d   %6d   %11d   %0s",
                     bb, gf, span, obstab[bsel], dutslow[bsel],
                     (obstab[bsel] >= dutslow[bsel]) ? "contained"
                                                     : "INADMISSIBLE");
            if (!(obstab[bsel] >= dutslow[bsel])) begin
                n_inadm = n_inadm + 1;
                if (span == gf) n_inadm_single = n_inadm_single + 1;
            end
        end
        $display("      inadmissible among the 13 probed: %0d", n_inadm);
        chk("A7 all nine single-transition bytes are inadmissible, not two",
            n_inadm_single == 9);
        t_ok = 1;
        for (bsel = 9; bsel < NB; bsel = bsel + 1)
            if (!(obstab[bsel] >= dutslow[bsel])) t_ok = 0;
        chk("A7b the four multi-transition control bytes stay admissible", t_ok);
        chk("A7c exactly the single-transition bytes fail: no other byte probed does",
            n_inadm == n_inadm_single);
        $display("      -> the F7 admissible set is 256 - 9 = 247/256, not 252/256:");
        $display("         the 2026-09-29 V4 figure counted only the two bytes whose");
        $display("         own DUT limit coincides with the pair-measured window.");
        $display("");

        // ------------------------------------------------------------------
        // A8  GOLDEN REGRESSION.  The only check in this file that pins the
        //     measured NUMBERS rather than an inequality over them.  Added
        //     after mutation testing showed M2 (bit boundary at 15 ticks)
        //     and M3 (RX synchroniser bypassed) both moved the window and
        //     left the RESULT tally bit-identical: every other check here
        //     is a bound, and a bound does not notice a change that stays
        //     inside it.
        // ------------------------------------------------------------------
        gold_slow[0]=655; gold_fast[0]=450;   gold_slow[1]=640; gold_fast[1]=465;
        gold_slow[2]=690; gold_fast[2]=415;   gold_slow[3]=675; gold_fast[3]=430;
        gold_slow[4]=605; gold_fast[4]=500;   gold_slow[5]=655; gold_fast[5]=450;
        gold_slow[6]=640; gold_fast[6]=465;   gold_slow[7]=625; gold_fast[7]=485;
        gold_slow[8]=590; gold_fast[8]=520;   gold_slow[9]=640; gold_fast[9]=465;
        gold_slow[10]=625; gold_fast[10]=485; gold_slow[11]=605; gold_fast[11]=500;
        gold_slow[12]=615; gold_fast[12]=490; gold_slow[13]=595; gold_fast[13]=510;
        gold_slow[14]=580; gold_fast[14]=525; gold_slow[15]=630; gold_fast[15]=475;
        gold_slow[16]=585; gold_fast[16]=525; gold_slow[17]=565; gold_fast[17]=540;
        gold_slow[18]=620; gold_fast[18]=490; gold_slow[19]=600; gold_fast[19]=505;
        gold_slow[20]=605; gold_fast[20]=505; gold_slow[21]=585; gold_fast[21]=520;
        gold_slow[22]=570; gold_fast[22]=540; gold_slow[23]=620; gold_fast[23]=485;

        gold_byte[0]=650;  gold_byte[1]=725;  gold_byte[2]=825;
        gold_byte[3]=975;  gold_byte[4]=1175; gold_byte[5]=1475;
        gold_byte[6]=1975; gold_byte[7]=2950; gold_byte[8]=5925;
        gold_byte[9]=650;  gold_byte[10]=650; gold_byte[11]=725;
        gold_byte[12]=650;

        $display("A8  golden regression against the 2026-10-01 measured tables");
        n_gold_diff = 0;
        for (i = 0; i < NDIV*NQ; i = i + 1) begin
            if (slow_t[i] != gold_slow[i] || fast_t[i] != gold_fast[i]) begin
                n_gold_diff = n_gold_diff + 1;
                $display("      div %0d phase %0d: (%0d,%0d) golden (%0d,%0d)",
                         divtab[i/NQ], i%NQ, slow_t[i], fast_t[i],
                         gold_slow[i], gold_fast[i]);
            end
        end
        for (bsel = 0; bsel < NB; bsel = bsel + 1) begin
            if (dutslow[bsel] != gold_byte[bsel]) begin
                n_gold_diff = n_gold_diff + 1;
                $display("      byte 0x%02h: %0d golden %0d",
                         bytab[bsel][7:0], dutslow[bsel], gold_byte[bsel]);
            end
        end
        $display("      entries differing from golden: %0d of %0d",
                 n_gold_diff, NDIV*NQ + NB);
        chk("A8 all 37 measured window entries match the committed golden table",
            n_gold_diff == 0);
        $display("");

        $display("------------------------------------------------------------------------------");
        $display("frames driven: %0d", trial_cnt);
        $display("RESULT %0d/%0d checks passed, %0d failed",
                 pass_cnt, pass_cnt + fail_cnt, fail_cnt);
        $display("  (P3, P5 and A2a are PRE-REGISTERED PREDICTIONS OF MINE THAT FAILED.");
        $display("   They are left in the suite as failing checks rather than deleted:");
        $display("   the file's purpose is to decide them, and a prediction");
        $display("   removed once refuted cannot be audited later.)");
        $display("------------------------------------------------------------------------------");
        $finish;
    end

endmodule
