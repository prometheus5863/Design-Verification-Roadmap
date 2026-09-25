// examples/phase6_rx_pin_driver/uart_rx_pin_tb.v
//
// CONSTRAINED-RANDOM STIMULUS DRIVEN AT THE RX PIN, FROM AN INDEPENDENT
// TIMEBASE -- the top item of the 2026-09-24 "Not yet covered" list, created
// by that session's mutant M5 and subsuming the standalone RX bit-driver item
// open since the Phase 4 milestone.
//
// WHY THIS BENCH HAD TO EXIST, IN ONE PARAGRAPH
// --------------------------------------------
// Every UART bench in this repo so far has run in LOOPBACK, where CTRL.en
// routes tx internally back to the receiver.  On 2026-09-24 the mutation test
// injected M5 -- "BAUD_DIV ignored by the baud generator" -- and it ESCAPED,
// as predicted, with every data check passing.  The reason is structural, not
// a gap in the stimulus: in loopback the TX and RX engines share ONE baud
// generator, so a wrong divisor desynchronises nothing.  Both sides are wrong
// together and the data is perfect.  NO LOOPBACK BENCH, AT ANY LEVEL OF
// SOPHISTICATION, CAN DETECT A BAUD-RATE ERROR.  The only thing that can is a
// driver with its own timebase, which is this file.
//
// Consequences, all of which this bench turns from "unreachable" into
// measured:
//   * F7's baud tolerance -- a number the verification plan requires and no
//     bench in this repo has ever produced, because in loopback the tolerance
//     is infinite.
//   * frame errors     -- loopback's tx never emits a bad stop bit.
//   * parity errors    -- loopback's tx never emits wrong parity.
//   * the start-bit glitch filter -- loopback's tx never emits a runt pulse.
//   * overrun          -- reachable in loopback in principle, but only by
//     racing the register interface; at the pin it is deterministic.
//
// THE INDEPENDENT TIMEBASE, CONCRETELY
// ------------------------------------
// The DUT's bit period is 16*(BAUD_DIV+1) clk cycles.  The driver does not
// use that number: it holds its OWN bit period as a real, `drv_bit_ns`, and
// sets it to the DUT's nominal period scaled by (1 + eps).  eps is the
// fractional baud mismatch, swept in per-mille steps.  Nothing in the driver
// reads the DUT's baud counter, its os_tick, or its clock -- it only toggles
// `rx` on its own schedule, exactly as a real remote transmitter would.
//
// WHAT THE DUT'S SAMPLING SCHEME PREDICTS (pre-registered, scored at the end)
// -------------------------------------------------------------------------
// The RX engine detects a falling edge in RX_IDLE, confirms the start bit at
// oversample position 8, then samples data bit k at position 8 of its own
// window.  Counting bit periods from the detected edge, the sample points are
// start 0.5, data 1.5 .. 8.5, parity 9.5, stop 9.5 or 10.5.  A frame is
// received correctly while the accumulated drift at the LAST sampled bit
// stays inside half a bit period, and the last sampled bit is the STOP bit,
// because the stop-bit check sets frame_err:
//
//   P1  8N1 (stop sampled at 9.5):  |eps| threshold ~ 0.5/9.5 = 5.3%
//   P2  8E1 (stop sampled at 10.5): |eps| threshold ~ 0.5/10.5 = 4.8%,
//       i.e. STRICTLY TIGHTER than P1 -- adding parity costs tolerance,
//       because it pushes the last sample one bit further from the resync.
//   P3  8N2: the same as 8N1 to first order.  The second stop bit is sampled
//       at 10.5, but a late second stop bit is still HIGH (the line idles
//       high), so drifting off its window cannot produce a 0 -- the extra
//       stop bit should cost NOTHING.  Stated as a prediction of no effect so
//       that it can fail.
//   P4  The measured thresholds land BELOW the ideal ones, by up to one
//       oversample tick (1/16 = 6.25% of a bit, so ~0.6% of eps at 9.5 bit
//       periods), because the DUT's free-running oversample counter is not
//       phase-aligned to the arriving edge and its rx_sync adds a clk of
//       delay.  Predicted measured range: 3.5% to 5.3% for 8N1.
//   P5  The fast and slow thresholds are ASYMMETRIC, for the same
//       quantisation reason, by at least 0.2% of eps.
//   P6  This bench DETECTS M5 (BAUD_DIV ignored), the loopback escape.
//       Scored by run_mutation_tests.sh, not here.
//
// Run:  bash examples/phase6_rx_pin_driver/run_rx_pin.sh
// Plain Verilog-2001 (plus $random), so it runs on this repo's pinned
// Icarus 10.3 build.  No classes anywhere.

`timescale 1ns / 1ps

module uart_rx_pin_tb;

    // -----------------------------------------------------------------
    // Clock, reset, DUT
    // -----------------------------------------------------------------
    localparam real CLK_NS = 10.0;
    localparam integer BAUD_DIV_CFG = 1;                      // os tick every 2 clk
    localparam real BIT_NS_NOM = CLK_NS * 16.0 * (BAUD_DIV_CFG + 1);   // 320.0 ns

    reg clk = 1'b0, rst_n = 1'b0;
    always #(CLK_NS / 2.0) clk = ~clk;

    reg  [3:0] paddr = 4'h0;
    reg  [7:0] pwdata = 8'h00;
    reg        pwrite = 1'b0, psel = 1'b0, penable = 1'b0;
    wire [7:0] prdata;
    wire       pready, tx, irq;
    reg        rx = 1'b1;          // idle high; THIS is the pin we drive

    uart_controller dut (
        .clk(clk), .rst_n(rst_n),
        .paddr(paddr), .pwdata(pwdata), .prdata(prdata),
        .pwrite(pwrite), .psel(psel), .penable(penable), .pready(pready),
        .tx(tx), .rx(rx), .irq(irq)
    );

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TXD  = 4'h3, ADDR_RXD    = 4'h4, ADDR_INTEN = 4'h5;
    localparam PAR_NONE = 2'b00, PAR_EVEN = 2'b01, PAR_ODD = 2'b10;

    // STATUS bit positions
    localparam SB_TXFULL = 0, SB_TXEMPTY = 1, SB_RXFULL = 2, SB_RXAVAIL = 3,
               SB_FRAMEERR = 4, SB_PARERR = 5, SB_OVRERR = 6;

    integer checks = 0, errors = 0;
    reg [7:0] rd_data;

    task fail(input [8*72:1] what);
        begin
            errors = errors + 1;
            $display("  ** FAIL: %0s   (t=%0t)", what, $time);
        end
    endtask

    task check_eq(input [31:0] got, input [31:0] exp, input [8*56:1] what);
        begin
            checks = checks + 1;
            if (got !== exp) begin
                errors = errors + 1;
                $display("  ** FAIL: %0s  got=%0h exp=%0h  (t=%0t)",
                         what, got, exp, $time);
            end
        end
    endtask

    // -----------------------------------------------------------------
    // APB register access
    // -----------------------------------------------------------------
    task apb_write(input [3:0] a, input [7:0] d);
        begin
            @(posedge clk); paddr <= a; pwdata <= d; pwrite <= 1'b1; psel <= 1'b1;
            @(posedge clk); penable <= 1'b1;
            @(posedge clk); psel <= 1'b0; penable <= 1'b0; pwrite <= 1'b0;
        end
    endtask

    task apb_read(input [3:0] a);
        begin
            @(posedge clk); paddr <= a; pwrite <= 1'b0; psel <= 1'b1;
            @(posedge clk); penable <= 1'b1;
            @(negedge clk); rd_data = prdata;
            @(posedge clk); psel <= 1'b0; penable <= 1'b0;
        end
    endtask

    task configure(input en, input [1:0] par, input two_stop, input lb);
        begin
            apb_write(ADDR_BAUD, BAUD_DIV_CFG[7:0]);
            apb_write(ADDR_CTRL, {3'b000, lb, two_stop, par, en});
        end
    endtask

    // Clearing the sticky error bits is a STATUS READ (see the RTL's
    // IMPLEMENTATION DECISION note).  Every trial starts from a clean slate,
    // because a leftover error bit from the previous trial would make the
    // tolerance search report the FIRST failure forever after.
    task clear_errors;
        begin
            apb_read(ADDR_STATUS);
            apb_read(ADDR_STATUS);
        end
    endtask

    // -----------------------------------------------------------------
    // THE PIN DRIVER.  Its only timebase is drv_bit_ns.
    // -----------------------------------------------------------------
    // bad_stop: drive the (first) stop bit LOW instead of high.
    // bad_par : invert the parity bit that would otherwise be correct.
    task drive_frame(input [7:0] data, input [1:0] par, input two_stop,
                     input real drv_bit_ns, input bad_stop, input bad_par);
        integer i;
        reg p;
        begin
            rx = 1'b0;                       // start bit
            #(drv_bit_ns);
            for (i = 0; i < 8; i = i + 1) begin
                rx = data[i];                // LSB first
                #(drv_bit_ns);
            end
            if (par != PAR_NONE) begin
                p = (par == PAR_EVEN) ? ^data : ~(^data);
                rx = bad_par ? ~p : p;
                #(drv_bit_ns);
            end
            rx = bad_stop ? 1'b0 : 1'b1;     // stop 1
            #(drv_bit_ns);
            if (two_stop) begin
                rx = 1'b1;                   // stop 2
                #(drv_bit_ns);
            end
            rx = 1'b1;                       // return to idle
        end
    endtask

    // A runt low pulse, shorter than half a bit: the RX_START mid-bit
    // re-check must discard it.
    task drive_glitch(input real width_ns);
        begin
            rx = 1'b0;
            #(width_ns);
            rx = 1'b1;
        end
    endtask

    task idle_gap(input real n_bits, input real drv_bit_ns);
        begin
            rx = 1'b1;
            #(n_bits * drv_bit_ns);
        end
    endtask

    // -----------------------------------------------------------------
    // Reference-checked reception of one frame
    // -----------------------------------------------------------------
    // Returns ok=1 when the byte arrived with the expected value and no error
    // bit set.  Used both as a checker (T2 onwards) and as the pass/fail
    // oracle of the tolerance search (T1), which is why it must NOT call
    // check_eq -- a tolerance sweep deliberately drives past the limit, and
    // counting those as failures would make the bench fail by design.
    task recv_expect(input [7:0] exp, output ok);
        reg [7:0] st;
        begin
            apb_read(ADDR_STATUS); st = rd_data;
            ok = 1'b1;
            if (!st[SB_RXAVAIL])                              ok = 1'b0;
            if (st[SB_FRAMEERR] || st[SB_PARERR] || st[SB_OVRERR]) ok = 1'b0;
            if (ok) begin
                apb_read(ADDR_RXD);
                if (rd_data !== exp) ok = 1'b0;
            end
        end
    endtask

    // Drain anything sitting in the RX FIFO plus the sticky bits, so the next
    // trial starts empty.  An undrained FIFO turns the NEXT trial's overrun
    // state into this trial's result.
    task drain;
        reg [7:0] st;
        integer guard;
        begin
            guard = 0;
            apb_read(ADDR_STATUS); st = rd_data;
            while (st[SB_RXAVAIL] && guard < 32) begin
                apb_read(ADDR_RXD);
                apb_read(ADDR_STATUS); st = rd_data;
                guard = guard + 1;
            end
            if (guard >= 32) fail("drain() did not empty the RX FIFO");
            clear_errors;
        end
    endtask

    // =================================================================
    // T0 -- MEASURE THE SAMPLE POINT, rather than believe the comment
    // =================================================================
    // The RTL says "16x oversample, sample at mid-bit (os position 8)", and
    // predictions P1..P5 above were derived from exactly that.  A hierarchical
    // probe on dut.rx_mid measures where the samples actually land, in units of
    // the DRIVER's bit period, timed from the driver's own falling edge.  This
    // costs four lines and it is the difference between predicting from a
    // comment and predicting from the design.
    real edge_t;
    real samp_off [0:11];        // offset of sample n, in bit periods
    integer n_samp = 0;
    reg     watch = 1'b0;

    always @(posedge clk)
        if (rst_n && watch && dut.rx_mid && n_samp < 12) begin
            samp_off[n_samp] = ($realtime - edge_t) / BIT_NS_NOM;
            n_samp = n_samp + 1;
        end

    real off_first, off_last;

    task measure_sample_point(input [1:0] par, input two_stop);
        integer i;
        begin
            configure(1'b1, par, two_stop, 1'b0);
            drain;
            n_samp = 0;
            watch  = 1'b1;
            edge_t = $realtime;
            drive_frame(8'h00, par, two_stop, BIT_NS_NOM, 1'b0, 1'b0);
            idle_gap(4.0, BIT_NS_NOM);
            watch = 1'b0;
            drain;
        end
    endtask
    // The three checks T0 exists to make, all against values the DUT's own
    // structure fixes exactly:
    //   * consecutive samples are EXACTLY one bit period apart (the receiver
    //     free-runs at its own rate once resynchronised)
    //   * there are exactly the number of samples the frame format implies
    //   * the offset is the same for every sample (no cumulative slip)
    task check_sample_geometry(input integer expect_n, input [8*32:1] what);
        integer i;
        real d, worst;
        begin
            checks = checks + 1;
            if (n_samp !== expect_n) begin
                errors = errors + 1;
                $display("  ** FAIL: %0s sample count %0d, expected %0d",
                         what, n_samp, expect_n);
            end else begin
                worst = 0.0;
                for (i = 1; i < expect_n; i = i + 1) begin
                    d = samp_off[i] - samp_off[i-1] - 1.0;
                    if (d < 0.0) d = -d;
                    if (d > worst) worst = d;
                end
                checks = checks + 1;
                if (worst > 1.0e-9) begin
                    errors = errors + 1;
                    $display("  ** FAIL: %0s sample spacing drifts by %0.3e bit",
                             what, worst);
                end
                $display("    %-10s n=%0d  first sample at %0.4f bit, last at %0.4f bit, spacing exactly 1 bit",
                         what, n_samp, samp_off[0], samp_off[n_samp-1]);
            end
        end
    endtask

    // =================================================================
    // T1 -- F7 BAUD TOLERANCE, MEASURED
    // =================================================================
    // For a configuration and a sign, walk eps outward in per-mille steps
    // until a frame is no longer received cleanly, and report the last eps
    // that worked.  FRAMES_PER_TRIAL > 1 matters: a single byte can survive a
    // marginal eps by luck of its bit pattern (a byte of all ones has no
    // sampled transition to get wrong), so each eps is tested with several
    // patterns including the two extremes.
    // eps is carried in BASIS POINTS (1 bp = 0.01%), because the 8N1-vs-8N2
    // comparison P3 makes is a two-step difference at 0.2% resolution and would
    // not be distinguishable from the grid.
    integer EPS_STEP_BP = 5;                 // 0.05% steps (overridable)
    localparam integer EPS_MAX_BP = 1200;    // give up at 12%
    localparam integer FRAMES_PER_TRIAL = 6;

    reg [7:0] pat [0:5];
    integer seed = 1;

    task measure_tolerance(input [1:0] par, input two_stop, input integer sgn,
                           output integer tol_bp);
        integer e, f;
        reg ok, all_ok;
        real bns;
        begin
            configure(1'b1, par, two_stop, 1'b0);   // LOOPBACK OFF
            tol_bp = -1;
            e = 0;
            all_ok = 1'b1;
            while (all_ok && e <= EPS_MAX_BP) begin
                bns = BIT_NS_NOM * (1.0 + sgn * e / 10000.0);
                drain;
                all_ok = 1'b1;
                for (f = 0; f < FRAMES_PER_TRIAL; f = f + 1) begin
                    drive_frame(pat[f], par, two_stop, bns, 1'b0, 1'b0);
                    idle_gap(3.0, bns);
                    recv_expect(pat[f], ok);
                    if (!ok) all_ok = 1'b0;
                    clear_errors;
                end
                if (all_ok) begin
                    tol_bp = e;
                    e = e + EPS_STEP_BP;
                end
            end
        end
    endtask

    // =================================================================
    // T2 -- constrained-random pin stimulus INSIDE the measured tolerance
    // =================================================================
    // The constraint set, by hand (no `constraint` blocks on Icarus 10.3):
    //   data      : unconstrained 8-bit
    //   eps       : uniform in [-tol_margin, +tol_margin] per-mille, where
    //               tol_margin is 60% of the tightest measured tolerance --
    //               a margin, so this test checks the INTERIOR of the region
    //               T1 measured and is not a second copy of the boundary
    //               search.  A bench that randomises right up to a measured
    //               limit fails intermittently and teaches nothing.
    //   gap       : uniform in [2, 9] bit periods of idle
    //   config    : one of the four (parity, stop) combinations
    // Every frame is self-checked against the reference byte.
    integer t2_frames = 0, t2_bad = 0;

    task crv_burst(input integer n, input integer tol_margin_bp);
        integer i, e, gap, cfgsel;
        reg [7:0] d;
        reg [1:0] par;
        reg ts, ok;
        real bns;
        begin
            for (i = 0; i < n; i = i + 1) begin
                d      = $random(seed);
                e      = ({$random(seed)} % (2 * tol_margin_bp + 1)) - tol_margin_bp;
                // {$random} FORCES UNSIGNED.  The first version of this line used
                // bare $random, whose result is SIGNED, so `% (2m+1)` can be
                // negative and the subtraction pushed eps to -7.2% with a margin of
                // 2.4% -- seven of twenty frames failed and the bench blamed the DUT.
                // A random generator that silently exceeds its own constraint is the
                // stimulus-side form of this repo's verdict-vs-checking class.
                gap    = 2 + (({$random(seed)} % 8));
                cfgsel = {$random(seed)} % 4;
                case (cfgsel)
                    0: begin par = PAR_NONE; ts = 1'b0; end
                    1: begin par = PAR_NONE; ts = 1'b1; end
                    2: begin par = PAR_EVEN; ts = 1'b0; end
                    default: begin par = PAR_ODD; ts = 1'b0; end
                endcase
                configure(1'b1, par, ts, 1'b0);
                drain;
                bns = BIT_NS_NOM * (1.0 + e / 10000.0);
                drive_frame(d, par, ts, bns, 1'b0, 1'b0);
                idle_gap(gap * 1.0, bns);
                recv_expect(d, ok);
                t2_frames = t2_frames + 1;
                checks = checks + 1;
                if (!ok) begin
                    t2_bad = t2_bad + 1;
                    errors = errors + 1;
                    $display("  ** FAIL: CRV frame %0d lost: data=%02h eps=%0d/10000 par=%0d two_stop=%0b (t=%0t)", i, d, e, par, ts, $time);
                end
            end
        end
    endtask

    // =================================================================
    // T3..T6 -- the error paths loopback cannot reach
    // =================================================================
    task test_frame_error;
        reg [7:0] st;
        begin
            configure(1'b1, PAR_NONE, 1'b0, 1'b0);
            drain;
            drive_frame(8'h5A, PAR_NONE, 1'b0, BIT_NS_NOM, 1'b1, 1'b0);  // stop = 0
            idle_gap(4.0, BIT_NS_NOM);
            apb_read(ADDR_STATUS); st = rd_data;
            check_eq(st[SB_FRAMEERR], 1'b1, "T3 frame_err set by a low stop bit");
            check_eq(st[SB_PARERR],   1'b0, "T3 parity_err not set by a frame error");
            clear_errors;
            apb_read(ADDR_STATUS);
            check_eq(rd_data[SB_FRAMEERR], 1'b0, "T3 frame_err cleared by STATUS read");
        end
    endtask

    task test_parity_error;
        reg [7:0] st;
        integer m;
        begin
            for (m = 0; m < 2; m = m + 1) begin
                configure(1'b1, m ? PAR_ODD : PAR_EVEN, 1'b0, 1'b0);
                drain;
                // correct parity first: must NOT flag
                drive_frame(8'h3C, m ? PAR_ODD : PAR_EVEN, 1'b0, BIT_NS_NOM, 1'b0, 1'b0);
                idle_gap(4.0, BIT_NS_NOM);
                apb_read(ADDR_STATUS); st = rd_data;
                check_eq(st[SB_PARERR], 1'b0,
                         m ? "T4 odd parity correct -> no parity_err"
                           : "T4 even parity correct -> no parity_err");
                drain;
                // then inverted parity on the same byte: must flag
                drive_frame(8'h3C, m ? PAR_ODD : PAR_EVEN, 1'b0, BIT_NS_NOM, 1'b0, 1'b1);
                idle_gap(4.0, BIT_NS_NOM);
                apb_read(ADDR_STATUS); st = rd_data;
                check_eq(st[SB_PARERR], 1'b1,
                         m ? "T4 odd parity inverted -> parity_err"
                           : "T4 even parity inverted -> parity_err");
                clear_errors;
            end
        end
    endtask

    task test_overrun;
        reg [7:0] st;
        integer i;
        begin
            configure(1'b1, PAR_NONE, 1'b0, 1'b0);
            drain;
            // 8-deep FIFO: nine frames with no read must overrun on the ninth
            for (i = 0; i < 9; i = i + 1) begin
                drive_frame(8'hA0 + i[7:0], PAR_NONE, 1'b0, BIT_NS_NOM, 1'b0, 1'b0);
                idle_gap(2.0, BIT_NS_NOM);
            end
            apb_read(ADDR_STATUS); st = rd_data;
            check_eq(st[SB_OVRERR], 1'b1, "T5 overrun_err set by a 9th frame");
            check_eq(st[SB_RXFULL], 1'b1, "T5 rx_full set with 8 queued");
            // the FIRST eight must be intact -- overrun DROPS, does not overwrite
            clear_errors;
            for (i = 0; i < 8; i = i + 1) begin
                apb_read(ADDR_RXD);
                check_eq(rd_data, 8'hA0 + i[7:0], "T5 queued byte preserved under overrun");
            end
            apb_read(ADDR_STATUS);
            check_eq(rd_data[SB_RXAVAIL], 1'b0, "T5 FIFO empty after 8 reads");
        end
    endtask

    task test_glitch_filter;
        reg [7:0] st;
        begin
            configure(1'b1, PAR_NONE, 1'b0, 1'b0);
            drain;
            // a runt 3/16-bit low pulse: shorter than the mid-bit re-check
            drive_glitch(BIT_NS_NOM * 3.0 / 16.0);
            idle_gap(14.0, BIT_NS_NOM);
            apb_read(ADDR_STATUS); st = rd_data;
            check_eq(st[SB_RXAVAIL],  1'b0, "T6 runt pulse queues no byte");
            check_eq(st[SB_FRAMEERR], 1'b0, "T6 runt pulse sets no frame_err");
            // and the receiver must still be alive afterwards
            drain;
            drive_frame(8'hC3, PAR_NONE, 1'b0, BIT_NS_NOM, 1'b0, 1'b0);
            idle_gap(4.0, BIT_NS_NOM);
            apb_read(ADDR_STATUS);
            check_eq(rd_data[SB_RXAVAIL], 1'b1, "T6 receiver alive after a glitch");
            apb_read(ADDR_RXD);
            check_eq(rd_data, 8'hC3, "T6 byte after a glitch is correct");
        end
    endtask

    // =================================================================
    // T1b -- the slow-side failure is EXACTLY "data bit 7 is 0"
    // =================================================================
    // Beyond the slow limit the stop-bit sample lands in DRIVER BIT 8, which
    // carries data bit 7.  So frame_err must appear for every byte with
    // data[7] == 0 and for NO byte with data[7] == 1 -- an exactly known
    // outcome, not a range, and one no plausibility check would have produced.
    // The data itself must still be correct in BOTH cases, because every data
    // sample is bounded more loosely than the stop sample.
    //
    // eps = +7.5% is used rather than a step past the measured limit: one
    // oversample tick of edge phase moves that limit by 0.69% of eps, so a
    // trial just past it is phase-dependent and would make this exact test
    // intermittent.  7.5% clears BOTH phases (6.25% and 6.60%).
    // 6.80%: above BOTH phases' stop-bit limits (6.25% and 6.59%) and below
    // the tightest DATA-bit-7 limit (off/8 = 7.03%).  The first version used
    // 7.50%, which is past off/8, so data bit 7 was mis-sampled too and every
    // byte came back with bit 7 replaced by bit 6 -- the test failed while its
    // headline prediction passed, which is how the STAIRCASE below was found.
    localparam integer EPS_PAST_SLOW_BP = 680;

    task test_slow_boundary_is_bit7;
        integer i, n_ferr_lo, n_ferr_hi;
        reg [7:0] d, st;
        real bns;
        begin
            configure(1'b1, PAR_NONE, 1'b0, 1'b0);
            bns = BIT_NS_NOM * (1.0 + EPS_PAST_SLOW_BP / 10000.0);
            n_ferr_lo = 0; n_ferr_hi = 0;
            for (i = 0; i < 16; i = i + 1) begin
                // eight bytes with bit7 = 0, eight with bit7 = 1, same low bits
                d = (i < 8) ? {1'b0, i[2:0], 4'hA} : {1'b1, i[2:0], 4'hA};
                drain;
                drive_frame(d, PAR_NONE, 1'b0, bns, 1'b0, 1'b0);
                idle_gap(4.0, bns);
                apb_read(ADDR_STATUS); st = rd_data;
                if (st[SB_FRAMEERR]) begin
                    if (d[7]) n_ferr_hi = n_ferr_hi + 1;
                    else      n_ferr_lo = n_ferr_lo + 1;
                end
                if (st[SB_RXAVAIL]) begin
                    apb_read(ADDR_RXD);
                    check_eq(rd_data, d, "T1b data still correct past the slow limit");
                end else begin
                    fail("T1b no byte queued past the slow limit");
                end
                clear_errors;
            end
            $display("    at eps = +%0.2f%%: frame_err on %0d/8 bytes with data[7]=0, %0d/8 with data[7]=1",
                     EPS_PAST_SLOW_BP / 100.0, n_ferr_lo, n_ferr_hi);
            check_eq(n_ferr_lo, 8, "T1b frame_err on EVERY byte with data[7]=0");
            check_eq(n_ferr_hi, 0, "T1b frame_err on NO byte with data[7]=1");
        end
    endtask

    // =================================================================
    // T1c -- THE DEGRADATION STAIRCASE, an exact consequence with no free
    //        parameters (unpredicted; found by T1b's first version failing)
    // =================================================================
    // Sample i drifts out of driver bit i when eps > off/i, so as eps grows the
    // frame does not "stop working" -- it fails one sample at a time, from the
    // LAST sample backwards, at thresholds off/9, off/8, off/7, ... and each
    // failed sample reads the value of the PRECEDING bit.  With off measured in
    // T0 that is a table of numbers, not a description:
    //
    //     i=9 (stop1)    off/9  = 6.25%   frame_err, data intact
    //     i=8 (data 7)   off/8  = 7.03%   bit 7 <- bit 6
    //     i=7 (data 6)   off/7  = 8.04%   bit 6 <- bit 5 as well
    //     i=6 (data 5)   off/6  = 9.38%   and so on
    //
    // The check is that the number of corrupted data bits equals the number of
    // thresholds crossed.  The probe byte must be 0xAA: EVERY adjacent bit pair
    // has to differ, or a substitution is invisible.  The first version used
    // 0x2A, whose bits 7 and 6 are both 0, so the bit7 <- bit6 substitution
    // changed nothing and the staircase read one step low at every point.  A
    // stimulus value that cannot show the effect being counted is the
    // stimulus-side twin of 2026-09-24's unreachable coverage bin.
    //
    // The eps points are chosen to clear BOTH edge phases: each sits above
    // off_hi/i and below off_lo/(i-1), so the predicted count is
    // phase-independent and the check is exact rather than intermittent.
    task test_degradation_staircase;
        integer k, i, ncorrupt, pred;
        reg [7:0] got, d;
        real bns, epsf;
        integer eps_bp;
        begin
            configure(1'b1, PAR_NONE, 1'b0, 1'b0);
            d = 8'hAA;
            $display("    off = %0.4f .. %0.4f bit; byte 0xAA; predicted corrupt-bit count = #{i in 1..8 : eps > off_hi/i}",
                     off_line_lo, off_line_hi);
            $display("      %8s %10s %10s %10s   %s", "eps", "got", "corrupt", "predicted", "");
            for (k = 0; k < 5; k = k + 1) begin
                case (k)
                    0: eps_bp =  680;   // past stop1 only        -> 0 data bits
                    1: eps_bp =  770;   // past off/8             -> 1
                    2: eps_bp =  870;   // past off/7             -> 2
                    3: eps_bp = 1050;   // past off/6             -> 3
                    default: eps_bp = 1250;  // past off/5        -> 4
                endcase
                epsf = eps_bp / 10000.0;
                bns  = BIT_NS_NOM * (1.0 + epsf);
                drain;
                drive_frame(d, PAR_NONE, 1'b0, bns, 1'b0, 1'b0);
                idle_gap(4.0, bns);
                apb_read(ADDR_STATUS);
                if (!rd_data[SB_RXAVAIL]) begin
                    $display("      %7.2f%%  (no byte queued)", epsf * 100.0);
                    clear_errors;
                end else begin
                    apb_read(ADDR_RXD); got = rd_data;
                    ncorrupt = 0;
                    for (i = 0; i < 8; i = i + 1)
                        if (got[i] !== d[i]) ncorrupt = ncorrupt + 1;
                    // predicted: data bit (i-1) fails when eps > off/i, i = 8 down to 1
                    pred = 0;
                    for (i = 8; i >= 1; i = i - 1)
                        if (epsf > off_line_hi / (i * 1.0)) pred = pred + 1;
                    $display("      %7.2f%%   %8h %10d %10d   %s", epsf * 100.0,
                             got, ncorrupt, pred,
                             (ncorrupt == pred) ? "" : "<-- MISMATCH");
                    checks = checks + 1;
                    if (ncorrupt !== pred) begin
                        errors = errors + 1;
                        $display("  ** FAIL: staircase at eps=%0d bp: %0d corrupt bits, predicted %0d",
                                 eps_bp, ncorrupt, pred);
                    end
                    clear_errors;
                end
            end
        end
    endtask

    // =================================================================
    // MAIN
    // =================================================================
    integer tol_8n1_p, tol_8n1_m, tol_8n2_p, tol_8n2_m;
    integer tol_8e1_p, tol_8e1_m, tol_8o1_p, tol_8o1_m;
    integer tightest, margin;
    real off_line_lo, off_line_hi;
    integer derived_slow_lo_bp, derived_slow_hi_bp;
    integer derived_fast_lo_bp, derived_fast_hi_bp;
    integer p1_ok, p2_ok, p3_ok, p4_ok, p5_ok;
    integer n_crv;

    initial begin
        if (!$value$plusargs("seed=%d", seed)) seed = 1;
        if (!$value$plusargs("frames=%d", n_crv)) n_crv = 40;
        if (!$value$plusargs("epsstep=%d", EPS_STEP_BP)) EPS_STEP_BP = 5;

        pat[0] = 8'h00; pat[1] = 8'hFF; pat[2] = 8'hAA;
        pat[3] = 8'h55; pat[4] = 8'h01; pat[5] = 8'h80;

        $display("==============================================================");
        $display("UART RX-PIN DRIVER, INDEPENDENT TIMEBASE   seed=%0d", seed);
        $display("  DUT bit period : %0.1f ns  (16 x (BAUD_DIV=%0d + 1) x %0.1f ns)",
                 BIT_NS_NOM, BAUD_DIV_CFG, CLK_NS);
        $display("  loopback       : OFF for every test in this file");
        $display("==============================================================");

        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);

        // -------------------------------------------------------------
        $display("\n--- T0: where does the DUT actually sample? ---");
        measure_sample_point(PAR_NONE, 1'b0);
        check_sample_geometry(10, "8N1");
        off_first = samp_off[0];
        off_last  = samp_off[9];
        measure_sample_point(PAR_EVEN, 1'b0);
        check_sample_geometry(11, "8E1");
        measure_sample_point(PAR_NONE, 1'b1);
        check_sample_geometry(11, "8N2");
        $display("    The RTL comment says \"sample at mid-bit (os position 8)\" = 0.5000 bit.");
        $display("    Measured: %0.4f bit -- LATE by %0.4f bit (%0.1f oversample ticks),",
                 off_first, off_first - 0.5, (off_first - 0.5) * 16.0);
        $display("    because rx_os starts counting at the first os_tick AFTER edge detection");
        $display("    and rx_sync adds a clk.  Predictions P1/P4 were derived from the comment.");

        // -------------------------------------------------------------
        $display("\n--- T1: F7 baud tolerance, measured (%0.2f%% steps) ---",
                 EPS_STEP_BP / 100.0);
        measure_tolerance(PAR_NONE, 1'b0, +1, tol_8n1_p);
        measure_tolerance(PAR_NONE, 1'b0, -1, tol_8n1_m);
        measure_tolerance(PAR_NONE, 1'b1, +1, tol_8n2_p);
        measure_tolerance(PAR_NONE, 1'b1, -1, tol_8n2_m);
        measure_tolerance(PAR_EVEN, 1'b0, +1, tol_8e1_p);
        measure_tolerance(PAR_EVEN, 1'b0, -1, tol_8e1_m);
        measure_tolerance(PAR_ODD,  1'b0, +1, tol_8o1_p);
        measure_tolerance(PAR_ODD,  1'b0, -1, tol_8o1_m);

        // SIGN CONVENTION, stated because it is easy to get backwards: eps > 0
        // LENGTHENS the driver's bit period, i.e. the remote transmitter is
        // SLOWER than the DUT expects.  eps < 0 is a FASTER transmitter.
        $display("  %-8s %12s %12s   %s", "config", "fast(eps<0)", "slow(eps>0)",
                 "last CHECKED sample");
        $display("  %-8s %11.2f%% %11.2f%%   %s", "8N1",
                 tol_8n1_m / 100.0, tol_8n1_p / 100.0, "d7 (fast) / stop1 (slow)");
        $display("  %-8s %11.2f%% %11.2f%%   %s", "8N2",
                 tol_8n2_m / 100.0, tol_8n2_p / 100.0, "d7 (fast) / stop2 (slow)");
        $display("  %-8s %11.2f%% %11.2f%%   %s", "8E1",
                 tol_8e1_m / 100.0, tol_8e1_p / 100.0, "parity (fast) / stop1 (slow)");
        $display("  %-8s %11.2f%% %11.2f%%   %s", "8O1",
                 tol_8o1_m / 100.0, tol_8o1_p / 100.0, "parity (fast) / stop1 (slow)");

        tightest = tol_8n1_p;
        if (tol_8n1_m < tightest) tightest = tol_8n1_m;
        if (tol_8n2_p < tightest) tightest = tol_8n2_p;
        if (tol_8n2_m < tightest) tightest = tol_8n2_m;
        if (tol_8e1_p < tightest) tightest = tol_8e1_p;
        if (tol_8e1_m < tightest) tightest = tol_8e1_m;
        if (tol_8o1_p < tightest) tightest = tol_8o1_p;
        if (tol_8o1_m < tightest) tightest = tol_8o1_m;
        $display("  tightest over all eight measurements: %0.2f%%", tightest / 100.0);

        // ---- AN INDEPENDENT ROUTE TO THE SAME NUMBER --------------------
        // With the sample point MEASURED in T0, the tolerance follows from
        // arithmetic, and the two routes are independent: one sweeps the driver
        // and watches the DUT fail, the other computes when sample i leaves
        // driver-bit i.  Sample i lands at (i + off) bit periods after the
        // driver's edge, and driver bit i spans [i, i+1]*(1+eps), so
        //     drifting EARLY out of bit i :  eps <=  off / i
        //     drifting LATE  into bit i+1 :  eps >= -(1 - off) / (i + 1)
        //
        // THREE CORRECTIONS THAT ARE NOT BOOKKEEPING, each measured:
        //
        // (1) `off` is not the offset of the SAMPLE, it is the offset of the
        //     LINE VALUE the sample sees, and rx_sync delays that by one clk.
        //     One clk is CLK_NS/BIT_NS_NOM = 1/32 bit here, which is 0.35% of
        //     eps at i = 9 -- larger than the sweep grid.  Without this term
        //     the derived slow limit is 6.60% against a swept 6.25%; with it,
        //     they agree exactly.
        // (2) The binding i DIFFERS BY DIRECTION, and that is the whole reason
        //     the tolerance is asymmetric.  Drifting LATE off a stop bit is
        //     harmless, because the line idles HIGH and a late sample of idle
        //     still reads 1.  So on the fast side the binding sample is the last
        //     one carrying a VALUE (data bit 7, or the parity bit), while on the
        //     slow side it is the LAST STOP BIT, whose early drift lands in a
        //     data bit that may be 0.  Not quantisation -- a property of
        //     idle-high framing.
        // (3) `off` is QUANTISED by the arrival edge's alignment to the DUT's
        //     free-running oversample counter, in 1/16-bit steps, and T0 sees it
        //     take both 0.5938 and 0.6250 across configurations.  One such step
        //     is 0.69% of eps at i = 9 -- FOURTEEN sweep grid steps.  So the
        //     tolerance is a BAND, not a number, and the 0.05% sweep resolution
        //     is finer than the phenomenon it measures.  The derived check below
        //     is therefore against the band, and quoting F7 to two decimals
        //     would be spurious precision.
        // off_line_hi is the MEASURED sample point minus one clk of rx_sync.
        // off_line_lo is one oversample tick below it: T0 sees the sample point
        // take two values one tick apart across configurations, because the
        // arrival edge's phase against the DUT's free-running counter is not
        // controlled, and the tolerance the sweep reports is the WORST phase the
        // six patterns happen to hit.  Deriving `lo` from the measurement rather
        // than writing 0.5625 matters: a hardcoded bound is a claim about this
        // RTL, and it inverted the band under a mutant that moves the sample
        // point -- the graphene repo's lesson of the same day, that a numeric
        // default is a claim about scale, in Verilog.
        off_line_hi = off_first - CLK_NS / BIT_NS_NOM;
        off_line_lo = off_line_hi - 1.0 / 16.0;
        derived_slow_lo_bp = $rtoi(off_line_lo * 10000.0 / 9.0);
        derived_slow_hi_bp = $rtoi(off_line_hi * 10000.0 / 9.0);
        derived_fast_lo_bp = $rtoi((1.0 - off_line_hi) * 10000.0 / 9.0);
        derived_fast_hi_bp = $rtoi((1.0 - off_line_lo) * 10000.0 / 9.0);
        $display("  derived from T0's measured sample point, no free parameters (8N1):");
        $display("      line-sample offset %0.4f .. %0.4f bit (one oversample tick of edge-phase quantisation, minus one clk of rx_sync)",
                 off_line_lo, off_line_hi);
        $display("      slow  eps <= off/9        = %0.2f%% .. %0.2f%%    swept: %0.2f%%",
                 derived_slow_lo_bp / 100.0, derived_slow_hi_bp / 100.0,
                 tol_8n1_p / 100.0);
        $display("      fast  eps >= -(1-off)/9   = -%0.2f%% .. -%0.2f%%   swept: -%0.2f%%",
                 derived_fast_lo_bp / 100.0, derived_fast_hi_bp / 100.0,
                 tol_8n1_m / 100.0);
        checks = checks + 1;
        if (tol_8n1_p < derived_slow_lo_bp - 2 * EPS_STEP_BP ||
            tol_8n1_p > derived_slow_hi_bp + 2 * EPS_STEP_BP) begin
            errors = errors + 1;
            $display("  ** FAIL: swept slow %0d bp outside the derived band %0d..%0d bp",
                     tol_8n1_p, derived_slow_lo_bp, derived_slow_hi_bp);
        end
        checks = checks + 1;
        if (tol_8n1_m < derived_fast_lo_bp - 2 * EPS_STEP_BP ||
            tol_8n1_m > derived_fast_hi_bp + 2 * EPS_STEP_BP) begin
            errors = errors + 1;
            $display("  ** FAIL: swept fast %0d bp outside the derived band %0d..%0d bp",
                     tol_8n1_m, derived_fast_lo_bp, derived_fast_hi_bp);
        end

        // -------------------------------------------------------------
        $display("\n--- T1b: the slow-side failure mode, predicted EXACTLY ---");
        test_slow_boundary_is_bit7;

        $display("\n--- T1c: the degradation staircase, exact and unpredicted ---");
        test_degradation_staircase;

        // -------------------------------------------------------------
        margin = (tightest * 6) / 10;
        $display("\n--- T2: constrained-random pin stimulus, %0d frames, |eps| <= %0.1f%% (60%% of tightest) ---", n_crv, margin / 100.0);
        crv_burst(n_crv, margin);
        $display("  frames driven %0d, lost %0d", t2_frames, t2_bad);

        $display("\n--- T3: framing error (loopback cannot produce one) ---");
        test_frame_error;
        $display("\n--- T4: parity error, both polarities ---");
        test_parity_error;
        $display("\n--- T5: RX overrun ---");
        test_overrun;
        $display("\n--- T6: start-bit glitch filter ---");
        test_glitch_filter;

        // -------------------------------------------------------------
        $display("\n--- PRE-REGISTERED PREDICTIONS, SCORED ---");
        // P1: 8N1 near the ideal 5.3%
        p1_ok = (tol_8n1_p >= 350 && tol_8n1_p <= 530) &&
                (tol_8n1_m >= 350 && tol_8n1_m <= 530);
        // P2: adding parity is STRICTLY tighter than 8N1
        p2_ok = (tol_8e1_p < tol_8n1_p) && (tol_8e1_m < tol_8n1_m) &&
                (tol_8o1_p < tol_8n1_p) && (tol_8o1_m < tol_8n1_m);
        // P3: the second stop bit costs nothing
        p3_ok = (tol_8n2_p == tol_8n1_p) && (tol_8n2_m == tol_8n1_m);
        // P4: measured below the ideal 5.3%
        p4_ok = (tol_8n1_p <= 530) && (tol_8n1_m <= 530);
        // P5: fast/slow asymmetry of at least 0.2%
        p5_ok = ((tol_8n1_p - tol_8n1_m) >= 20) || ((tol_8n1_m - tol_8n1_p) >= 20);
        $display("  P1 8N1 tolerance in 3.5%%..5.3%%                        %s",
                 p1_ok ? "PASS" : "FAIL");
        $display("  P2 parity STRICTLY tightens tolerance vs 8N1           %s",
                 p2_ok ? "PASS" : "FAIL");
        $display("  P3 a second stop bit costs NOTHING (null prediction)   %s",
                 p3_ok ? "PASS" : "FAIL");
        $display("  P4 measured tolerance below the ideal 5.3%%            %s",
                 p4_ok ? "PASS" : "FAIL");
        $display("  P5 fast/slow asymmetry >= 0.2%% of eps                 %s",
                 p5_ok ? "PASS" : "FAIL");
        $display("  (P6 -- this bench detects the BAUD_DIV mutant -- is scored by run_mutation_tests.sh)");
        $display("  Predictions are REPORTED, not asserted: a wrong prediction about");
        $display("  the DUT is a result, and failing the run on one would hide it.");

        $display("\n==============================================================");
        $display("  checks %0d   errors %0d", checks, errors);
        $display("  F7 BAUD TOLERANCE (the number the vplan requires and no");
        $display("  loopback bench in this repo could ever produce):");
        $display("      8N1  slow +%0.2f%%  /  fast -%0.2f%%", tol_8n1_p / 100.0, tol_8n1_m / 100.0);
        $display("      8E1  slow +%0.2f%%  /  fast -%0.2f%%", tol_8e1_p / 100.0, tol_8e1_m / 100.0);
        $display("  QUOTE IT AS A BAND, NOT A NUMBER: one oversample tick of");
        $display("  uncontrolled edge phase moves each limit by 0.69%% of eps, so the");
        $display("  defensible statement is 'better than +/-4.0%% in every configuration");
        $display("  measured, asymmetric, and tighter with parity than without'.");
        if (errors == 0) $display("RESULT: PASS");
        else             $display("RESULT: FAIL (%0d errors)", errors);
        $display("==============================================================");
        $finish;
    end

    // Global timeout: a hung pin driver must not look like a clean run.
    initial begin
        #40_000_000;
        $display("** FAIL: global timeout");
        $display("RESULT: FAIL (timeout)");
        $finish;
    end

endmodule
