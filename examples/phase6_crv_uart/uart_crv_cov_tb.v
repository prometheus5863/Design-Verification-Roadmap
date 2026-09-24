// examples/phase6_crv_uart/uart_crv_cov_tb.v
//
// CONSTRAINED-RANDOM, COVERAGE-DRIVEN UART stimulus -- the top item of the
// 2026-09-23 "Not yet covered" list, and the longest-standing one: every
// bench in this repo has been DIRECTED while the verification plan assigns
// most of its features to CRV.
//
// WHY THIS IS PLAIN VERILOG-2001, AND WHAT THAT COSTS
// ---------------------------------------------------
// Icarus 10.3 has no `rand`, no `constraint` blocks, no `covergroup` and no
// `solve ... before`. Writing "use SystemVerilog CRV" and not running it
// would be another instance of this repo's verdict-vs-checking class, so
// both mechanisms are built by hand -- and building them by hand is the
// point, because it makes explicit what the two language features actually
// do:
//
//   a constraint solver  -> REJECTION SAMPLING with a bounded attempt
//      budget. A real solver does better than draw-and-retry, but its
//      failure mode is the same one, and here it is visible rather than
//      hidden: pick_config_random counts rejected candidates and the run
//      FAILS if any single draw needs more than MAX_REJECT attempts. That
//      is the hand-built equivalent of a solver reporting an unsatisfiable
//      constraint set instead of hanging.
//   a covergroup  -> explicit bin-counter arrays, a closure check and a
//      printed report. 30 bins over 5 coverpoints and 2 crosses.
//
// THE MEASUREMENT THIS BENCH EXISTS TO MAKE
// -----------------------------------------
// Coverage-driven verification is usually described rather than measured.
// This bench runs in two modes over the SAME constraints and the SAME seed:
//
//   +steer=0  pure constrained-random throughout
//   +steer=1  constrained-random for STEER_AFTER transactions, after which
//             the generator reads its own coverage database and aims the
//             next configuration at the first unhit bin
//
// and reports TRANSACTIONS TO CLOSURE for each. That ratio is the whole
// argument for coverage-driven stimulus, and here it is a number a run
// produces rather than a claim a note makes.
//
// WHAT IS CHECKED -- every one a runtime comparison, never a comment
//   * every byte transmitted in loopback comes back, in order, unchanged
//   * the three sticky error bits read 0 on EVERY status read of a clean
//     loopback burst, so a spurious framing/parity/overrun error fails the
//     run even though no data check would notice it
//   * the reference queue is empty at the end of every burst
//   * the driver reads tx_full before every push and enqueues to the
//     reference model only when the DUT actually accepted the byte
//   * a per-burst watchdog sized from that burst's own baud divisor: a
//     burst that does not complete is a FAILURE, not a hang
//   * coverage closure is a PASS CRITERION, not a report line
//
// BURST SHAPE, and why the TX FIFO is filled with the UART disabled:
// tx_push is independent of CTRL.en, but the TX engine only pops in
// TX_IDLE when enabled. Pushing with en=0 therefore fills the FIFO without
// it draining, which is the only way this bench can observe STATUS.tx_full
// at all -- with en=1 the engine pops the first byte within a few cycles of
// the first push and tx_cnt never reaches 8. Getting that wrong is what
// would have made one coverage bin unreachable and the closure criterion
// permanently unsatisfiable.
//
// Usage:
//   source tools/setup_iverilog.sh          # source it, do NOT pipe it
//   iverilog -g2012 -o sim rtl/uart_controller.v \
//            examples/phase6_crv_uart/uart_crv_cov_tb.v
//   vvp sim +seed=1 +steer=0
//   vvp sim +seed=1 +steer=1

`timescale 1ns / 1ps

module uart_crv_cov_tb;

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TX = 4'h3, ADDR_RX = 4'h4, ADDR_INT_EN = 4'h5;

    localparam MAX_REJECT  = 200;   // unsatisfiable-constraint detector
    localparam STEER_AFTER = 24;    // pure-random transactions before steering

    reg        clk = 0, rst_n = 0;
    reg  [3:0] paddr = 0;
    reg  [7:0] pwdata = 0;
    wire [7:0] prdata;
    reg        pwrite = 0, psel = 0, penable = 0;
    wire       pready, tx, irq;
    reg        rx = 1'b1;

    uart_controller dut (
        .clk(clk), .rst_n(rst_n), .paddr(paddr), .pwdata(pwdata),
        .prdata(prdata), .pwrite(pwrite), .psel(psel), .penable(penable),
        .pready(pready), .tx(tx), .rx(rx), .irq(irq));

    always #5 clk = ~clk;

    integer errors  = 0;
    integer checks  = 0;
    integer seed    = 1;
    integer steer   = 0;
    integer max_tx  = 4000;

    // -----------------------------------------------------------------
    // APB access -- one process drives these, so plain tasks are safe
    // -----------------------------------------------------------------
    task apb_write(input [3:0] a, input [7:0] d);
        begin
            @(negedge clk); psel=1; pwrite=1; paddr=a; pwdata=d; penable=0;
            @(negedge clk); penable=1;
            @(negedge clk); psel=0; penable=0; pwrite=0;
        end
    endtask

    reg [7:0] rd_data;
    task apb_read(input [3:0] a);
        begin
            @(negedge clk); psel=1; pwrite=0; paddr=a; penable=0;
            @(negedge clk); penable=1; rd_data = prdata;
            @(negedge clk); psel=0; penable=0;
        end
    endtask

    task check_eq(input [31:0] got, input [31:0] exp, input [8*44:1] what);
        begin
            checks = checks + 1;
            if (got !== exp) begin
                errors = errors + 1;
                $display("  FAIL %0s: got 0x%0h, expected 0x%0h", what, got, exp);
            end
        end
    endtask

    // -----------------------------------------------------------------
    // COVERAGE MODEL -- 30 bins. This is the covergroup, written out.
    // -----------------------------------------------------------------
    integer cov_parity [0:2];   // none / even / odd
    integer cov_stop   [0:1];   // 1 stop / 2 stop
    integer cov_baud   [0:3];   // divisor 0..3
    integer cov_data   [0:5];   // 00 / FF / one-hot / AA-55 / even-pop / odd-pop
    integer cov_txq    [0:2];   // TX FIFO seen empty / partial / full
    integer cov_ps     [0:5];   // cross parity x stop
    integer cov_pd     [0:5];   // cross parity x popcount-parity of the byte

    localparam N_BINS = 3 + 2 + 4 + 6 + 3 + 6 + 6;   // = 30

    integer i;
    task cov_reset;
        begin
            for (i=0;i<3;i=i+1) cov_parity[i]=0;
            for (i=0;i<2;i=i+1) cov_stop[i]=0;
            for (i=0;i<4;i=i+1) cov_baud[i]=0;
            for (i=0;i<6;i=i+1) cov_data[i]=0;
            for (i=0;i<3;i=i+1) cov_txq[i]=0;
            for (i=0;i<6;i=i+1) cov_ps[i]=0;
            for (i=0;i<6;i=i+1) cov_pd[i]=0;
        end
    endtask

    function integer bins_hit;
        integer n, k;
        begin
            n = 0;
            for (k=0;k<3;k=k+1) if (cov_parity[k]>0) n=n+1;
            for (k=0;k<2;k=k+1) if (cov_stop[k]  >0) n=n+1;
            for (k=0;k<4;k=k+1) if (cov_baud[k]  >0) n=n+1;
            for (k=0;k<6;k=k+1) if (cov_data[k]  >0) n=n+1;
            for (k=0;k<3;k=k+1) if (cov_txq[k]   >0) n=n+1;
            for (k=0;k<6;k=k+1) if (cov_ps[k]    >0) n=n+1;
            for (k=0;k<6;k=k+1) if (cov_pd[k]    >0) n=n+1;
            bins_hit = n;
        end
    endfunction

    // Order matters: 0x00 also passes the (d & (d-1)) one-hot test, so it
    // has to be caught first. Getting this wrong would put every zero byte
    // in the one-hot bin and leave bin 0 permanently unhit.
    function [2:0] data_class(input [7:0] d);
        begin
            if      (d == 8'h00)               data_class = 3'd0;
            else if (d == 8'hFF)               data_class = 3'd1;
            else if ((d & (d - 8'd1)) == 8'd0) data_class = 3'd2;
            else if (d == 8'hAA || d == 8'h55) data_class = 3'd3;
            else if (^d == 1'b0)               data_class = 3'd4;
            else                               data_class = 3'd5;
        end
    endfunction

    function [7:0] byte_for_class(input [2:0] c);
        begin
            case (c)
                3'd0:    byte_for_class = 8'h00;
                3'd1:    byte_for_class = 8'hFF;
                3'd2:    byte_for_class = 8'h08;  // one-hot
                3'd3:    byte_for_class = 8'hAA;
                3'd4:    byte_for_class = 8'h33;  // popcount 4, not one-hot
                default: byte_for_class = 8'h07;  // popcount 3, not one-hot
            endcase
        end
    endfunction

    // -----------------------------------------------------------------
    // CONSTRAINED-RANDOM CONFIGURATION PICKER
    //
    // Constraints, every one enforced by rejection so that the rejection
    // count in the report is a real number:
    //   C1  parity_mode != 2'b11   (illegal encoding; never drive it)
    //   C2  baud_div <= 3          (drawn from 0..7, so C2 really rejects)
    //   C3  (parity, stop) != the previous burst's pair -- the constraint
    //       that forces configuration variety and makes the cross move
    //   C4  burst_len in [1, 8]
    // -----------------------------------------------------------------
    reg  [1:0] cfg_parity;
    reg        cfg_stop2;
    reg  [7:0] cfg_baud;
    integer    burst_len;

    reg  [1:0] prev_parity;
    reg        prev_stop2;
    integer    reject_total = 0;
    integer    reject_worst = 0;

    task pick_config_random;
        integer tries;
        integer pp, ss, bb;
        begin
            tries = 0;
            pp = 0; ss = 0; bb = 0;
            begin : draw
                forever begin
                    pp = $random(seed) & 32'h3;
                    ss = $random(seed) & 32'h1;
                    bb = $random(seed) & 32'h7;
                    tries = tries + 1;
                    if (pp == 3) begin
                        // C1 reject
                    end else if (bb > 3) begin
                        // C2 reject
                    end else if (pp == prev_parity && ss == prev_stop2) begin
                        // C3 reject
                    end else begin
                        disable draw;
                    end
                    if (tries > MAX_REJECT) begin
                        errors = errors + 1;
                        $display("  FAIL constraint set unsatisfiable: %0d rejected candidates in one draw", tries);
                        disable draw;
                    end
                end
            end
            reject_total = reject_total + (tries - 1);
            if ((tries - 1) > reject_worst) reject_worst = tries - 1;
            cfg_parity = pp[1:0];
            cfg_stop2  = ss[0];
            cfg_baud   = bb[7:0];
            burst_len  = 1 + (($random(seed) >>> 3) & 32'h7);   // C4
            prev_parity = cfg_parity;
            prev_stop2  = cfg_stop2;
        end
    endtask

    // -----------------------------------------------------------------
    // COVERAGE-DRIVEN STEERING
    //
    // The generator reads its own coverage database and aims the next
    // configuration at the first unhit bin, hardest coverpoint first. This
    // is all a coverage-driven flow does; what a commercial tool adds is
    // doing it without the engineer writing the bin-to-stimulus mapping by
    // hand, which is exactly what the loops below are.
    //
    // steer_byte == 9'h1FF means "leave the data random".
    // -----------------------------------------------------------------
    reg [8:0] steer_byte;

    task pick_config_steered;
        integer k;
        reg done;
        begin
            done = 0;
            steer_byte = 9'h1FF;
            burst_len  = 1 + (($random(seed) >>> 3) & 32'h7);

            for (k=0;k<6;k=k+1) if (!done && cov_pd[k]==0) begin
                cfg_parity = k / 2;                       // cross index = parity*2 + pop
                steer_byte = (k % 2) ? 9'h007 : 9'h033;   // odd / even popcount
                cfg_stop2  = $random(seed) & 32'h1;
                cfg_baud   = $random(seed) & 32'h3;
                done = 1;
            end
            for (k=0;k<6;k=k+1) if (!done && cov_ps[k]==0) begin
                cfg_parity = k / 2;
                cfg_stop2  = k % 2;
                cfg_baud   = $random(seed) & 32'h3;
                done = 1;
            end
            for (k=0;k<6;k=k+1) if (!done && cov_data[k]==0) begin
                steer_byte = {1'b0, byte_for_class(k[2:0])};
                cfg_parity = $random(seed) % 3;
                cfg_stop2  = $random(seed) & 32'h1;
                cfg_baud   = $random(seed) & 32'h3;
                done = 1;
            end
            for (k=0;k<4;k=k+1) if (!done && cov_baud[k]==0) begin
                cfg_baud   = k;
                cfg_parity = $random(seed) % 3;
                cfg_stop2  = $random(seed) & 32'h1;
                done = 1;
            end
            for (k=0;k<3;k=k+1) if (!done && cov_txq[k]==0) begin
                burst_len  = (k == 2) ? 8 : (k == 1) ? 3 : 1;
                cfg_parity = $random(seed) % 3;
                cfg_stop2  = $random(seed) & 32'h1;
                cfg_baud   = $random(seed) & 32'h3;
                done = 1;
            end
            if (!done) begin
                pick_config_random;
            end else begin
                if (cfg_parity == 2'b11) cfg_parity = 2'b00;   // C1 still holds
                if (cfg_baud > 8'd3)     cfg_baud   = 8'd3;    // C2 still holds
                prev_parity = cfg_parity;
                prev_stop2  = cfg_stop2;
            end
        end
    endtask

    // -----------------------------------------------------------------
    // REFERENCE MODEL -- an in-order queue of the bytes the DUT ACCEPTED
    // -----------------------------------------------------------------
    reg [7:0] expq [0:63];
    integer   exp_wr = 0, exp_rd = 0;

    integer total_tx     = 0;
    integer total_rx     = 0;
    integer closure_tx   = -1;
    integer push_skipped = 0;   // pushes not issued because tx_full was set

    reg [7:0] byte_to_send;
    reg [7:0] st;
    integer   pushed, got, guard, guard_limit, n;

    // The closure COUNTER and the closure CRITERION must read the same
    // database, and in the first version of this bench they did not: the
    // criterion called bins_hit() at the end of the run, while the counter
    // was only updated at push sites. A run whose last bin was filled by a
    // STATUS sample rather than by a push therefore printed
    // "TRANSACTIONS TO CLOSURE : NOT REACHED" and "RESULT: PASS" in the same
    // report (measured: seed=6, steer=1). Both statements were produced by
    // the same run and only one of them was true. Every coverage update now
    // goes through note_closure, so there is one definition of closure.
    task note_closure;
        begin
            if (closure_tx < 0)
                if (bins_hit() == N_BINS) closure_tx = total_tx;
        end
    endtask

    task sample_txq(input [7:0] s);
        begin
            if      (s[1]) cov_txq[0] = cov_txq[0] + 1;   // tx_empty
            else if (s[0]) cov_txq[2] = cov_txq[2] + 1;   // tx_full
            else           cov_txq[1] = cov_txq[1] + 1;   // partial
            note_closure;
        end
    endtask

    task run_burst;
        begin
            // ---- configure with the UART DISABLED so the FIFO can fill
            apb_write(ADDR_CTRL, 8'h00);
            apb_write(ADDR_BAUD, cfg_baud);
            apb_write(ADDR_CTRL, {3'b000, 1'b1, cfg_stop2, cfg_parity, 1'b0});

            cov_parity[cfg_parity]  = cov_parity[cfg_parity] + 1;
            cov_stop[cfg_stop2]     = cov_stop[cfg_stop2] + 1;
            cov_baud[cfg_baud[1:0]] = cov_baud[cfg_baud[1:0]] + 1;
            n = cfg_parity * 2 + cfg_stop2;
            cov_ps[n] = cov_ps[n] + 1;
            note_closure;

            // ---- push phase
            pushed = 0;
            for (n = 0; n < burst_len; n = n + 1) begin
                apb_read(ADDR_STATUS); st = rd_data;
                check_eq({29'd0, st[6:4]}, 32'd0, "push-phase status error bits clear");
                sample_txq(st);
                if (st[0]) begin
                    push_skipped = push_skipped + 1;
                end else begin
                    byte_to_send = (steer_byte <= 9'h0FF) ? steer_byte[7:0]
                                                          : ($random(seed) & 32'hFF);
                    cov_data[data_class(byte_to_send)] =
                        cov_data[data_class(byte_to_send)] + 1;
                    i = cfg_parity * 2 + (^byte_to_send);
                    cov_pd[i] = cov_pd[i] + 1;
                    note_closure;

                    apb_write(ADDR_TX, byte_to_send);
                    expq[exp_wr % 64] = byte_to_send;
                    exp_wr   = exp_wr + 1;
                    pushed   = pushed + 1;
                    total_tx = total_tx + 1;
                    note_closure;
                end
            end

            // ---- sample STATUS ONCE MORE, after the last push
            //
            // This line is the whole reason cp_txq.full is reachable, and
            // leaving it out is the bug this bench was first written with.
            // The push loop samples BEFORE each push, so with burst_len = 8
            // the last sample it takes is at occupancy 7 and STATUS.tx_full
            // is never observed -- the stimulus reached the state and the
            // covergroup simply never looked. A coverage hole can be a
            // SAMPLING-POINT defect rather than a stimulus gap, and the two
            // look identical in the report. It was caught only because
            // closure is a pass criterion here: 29/30 failed the run.
            apb_read(ADDR_STATUS); st = rd_data;
            check_eq({29'd0, st[6:4]}, 32'd0, "post-push status error bits clear");
            sample_txq(st);

            // ---- enable and drain
            apb_write(ADDR_CTRL, {3'b000, 1'b1, cfg_stop2, cfg_parity, 1'b1});

            got = 0;
            // one bit period is 16*(div+1) clk, a frame is at most 12 bits,
            // each loop pass costs at least 3 clk -> this budget is ~3x
            // generous, and overrunning it is a failure rather than a hang.
            guard_limit = burst_len * 16 * (cfg_baud + 1) * 13 + 2000;
            guard = 0;
            while (got < pushed && guard < guard_limit) begin
                guard = guard + 1;
                apb_read(ADDR_STATUS); st = rd_data;
                check_eq({29'd0, st[6:4]}, 32'd0, "drain-phase status error bits clear");
                sample_txq(st);
                if (st[3]) begin                     // rx_avail
                    apb_read(ADDR_RX);
                    check_eq({24'd0, rd_data}, {24'd0, expq[exp_rd % 64]},
                             "loopback byte matches reference model");
                    exp_rd   = exp_rd + 1;
                    got      = got + 1;
                    total_rx = total_rx + 1;
                end
            end

            if (guard >= guard_limit) begin
                errors = errors + 1;
                $display("  FAIL burst watchdog: %0d of %0d bytes returned (parity=%0d stop2=%0d div=%0d len=%0d)",
                         got, pushed, cfg_parity, cfg_stop2, cfg_baud, burst_len);
            end
            check_eq(exp_wr - exp_rd, 32'd0, "reference queue drained");
        end
    endtask

    // -----------------------------------------------------------------
    task report_coverage;
        integer h;
        begin
            h = bins_hit();
            $display("");
            $display("  ---------------- FUNCTIONAL COVERAGE REPORT ----------------");
            $display("  cp_parity  none=%0d even=%0d odd=%0d",
                     cov_parity[0], cov_parity[1], cov_parity[2]);
            $display("  cp_stop    one=%0d two=%0d", cov_stop[0], cov_stop[1]);
            $display("  cp_baud    d0=%0d d1=%0d d2=%0d d3=%0d",
                     cov_baud[0], cov_baud[1], cov_baud[2], cov_baud[3]);
            $display("  cp_data    00=%0d FF=%0d onehot=%0d AA55=%0d evenpop=%0d oddpop=%0d",
                     cov_data[0], cov_data[1], cov_data[2],
                     cov_data[3], cov_data[4], cov_data[5]);
            $display("  cp_txq     empty=%0d partial=%0d full=%0d",
                     cov_txq[0], cov_txq[1], cov_txq[2]);
            $display("  cross parity x stop      : %0d %0d %0d %0d %0d %0d",
                     cov_ps[0],cov_ps[1],cov_ps[2],cov_ps[3],cov_ps[4],cov_ps[5]);
            $display("  cross parity x popcount  : %0d %0d %0d %0d %0d %0d",
                     cov_pd[0],cov_pd[1],cov_pd[2],cov_pd[3],cov_pd[4],cov_pd[5]);
            $display("  bins hit: %0d/%0d  (%0d%%)", h, N_BINS, (100*h)/N_BINS);
            $display("  -----------------------------------------------------------");
        end
    endtask

    // -----------------------------------------------------------------
    initial begin
        if (!$value$plusargs("seed=%d",  seed))   seed   = 1;
        if (!$value$plusargs("steer=%d", steer))  steer  = 0;
        if (!$value$plusargs("maxtx=%d", max_tx)) max_tx = 4000;

        $display("================================================================");
        $display("CONSTRAINED-RANDOM / COVERAGE-DRIVEN UART STIMULUS");
        $display("  seed=%0d  steer=%0d  max_tx=%0d  bins=%0d",
                 seed, steer, max_tx, N_BINS);
        $display("================================================================");

        cov_reset;
        steer_byte  = 9'h1FF;
        prev_parity = 2'b11;   // an impossible pair, so C3 does not constrain
        prev_stop2  = 1'b1;    // the very first draw

        rst_n = 0; repeat (8) @(posedge clk); rst_n = 1; repeat (4) @(posedge clk);

        while (total_tx < max_tx && bins_hit() < N_BINS && errors == 0) begin
            steer_byte = 9'h1FF;
            if (steer != 0 && total_tx >= STEER_AFTER) pick_config_steered;
            else                                       pick_config_random;
            run_burst;
        end

        report_coverage;

        $display("");
        $display("  transactions driven      : %0d", total_tx);
        $display("  bytes received & checked : %0d", total_rx);
        $display("  pushes skipped (tx_full) : %0d", push_skipped);
        $display("  constraint rejections    : %0d total, %0d worst single draw, budget %0d",
                 reject_total, reject_worst, MAX_REJECT);
        if (closure_tx >= 0)
            $display("  TRANSACTIONS TO CLOSURE  : %0d   (steer=%0d)", closure_tx, steer);
        else
            $display("  TRANSACTIONS TO CLOSURE  : NOT REACHED in %0d  (steer=%0d)",
                     total_tx, steer);

        // Closure is a PASS CRITERION, not a report line.
        if (bins_hit() != N_BINS) begin
            errors = errors + 1;
            $display("  FAIL coverage closure: %0d of %0d bins", bins_hit(), N_BINS);
        end

        // And the two statements about closure must agree with each other.
        // This check exists because they once did not; an inconsistency
        // between two outputs of one run is the cheapest bug detector there
        // is, and it costs two lines.
        if ((bins_hit() == N_BINS) != (closure_tx >= 0)) begin
            errors = errors + 1;
            $display("  FAIL closure counter and closure criterion disagree: bins=%0d/%0d, closure_tx=%0d",
                     bins_hit(), N_BINS, closure_tx);
        end

        $display("");
        $display("  checks executed: %0d", checks);
        if (errors == 0) $display("  RESULT: PASS  (%0d/%0d checks)", checks, checks);
        else             $display("  RESULT: FAIL  (%0d failing checks of %0d)", errors, checks);
        $display("================================================================");
        if (errors != 0) $fatal(1, "uart_crv_cov_tb FAILED");
        $finish;
    end

endmodule
