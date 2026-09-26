// examples/phase6_baud_error_coverage/uart_baud_cov_tb.v
//
// A COVERAGE MODEL ON THE DRIVEN BAUD ERROR -- the top item of the
// 2026-09-25 "Not yet covered" list, created by that session's vplan v3
// revision:
//
//   "cp_baud_div's corner bins measure the divisor REGISTER, not the
//    tolerance; F7 needs bins on {0, within +/-2%, within +/-4%, beyond the
//    limit} and a closure criterion over them.  The stimulus now exists; the
//    coverage model does not, and 09-24's finding 9 is the warning attached
//    -- check a new bin is reachable BEFORE putting it in a closure
//    criterion."
//
// That warning is honoured literally here: every cross cell is classified
// reachable or unreachable by an EXPERIMENT (T4) before any of it enters the
// closure criterion (T5).  The pre-pass is not a formality.  It changes the
// answer, and it changes the item's own bin definition.
//
// WHY THE BINS THE ITEM ASKED FOR ARE THE WRONG BINS
// -------------------------------------------------
// "{0, within +/-2%, within +/-4%, beyond the limit}" mixes two kinds of
// edge.  2% and 4% are ABSOLUTE constants; "the limit" is a MEASURED
// PROPERTY OF THE DUT, and 2026-09-25 measured it as CONFIGURATION-DEPENDENT
// and as a BAND rather than a number:
//
//     8N1  slow +6.25%  fast -4.50%
//     8N2  slow +6.25%  fast -4.50%
//     8E1  slow +5.60%  fast -4.05%
//     8O1  slow +5.60%  fast -4.05%
//     ... each limit moved by 0.69% of eps by one oversample tick of
//         uncontrolled edge phase, which the driver does not control.
//
// So the absolute bin "within +/-4%" contains 4.00%, and 8E1's fast limit is
// 4.05% with a band reaching down to about 3.36%.  An absolute bin edge on a
// tolerance is a claim about scale that the DUT does not have to honour --
// the same fault class the graphene repo recorded as "a numeric default is a
// claim about scale", arriving here as a COVERAGE BIN rather than a
// threshold.  T2 and T3 measure whether it actually bites.
//
// WHAT A "BEYOND THE LIMIT" BIN CANNOT BE USED FOR
// -----------------------------------------------
// The tempting closure criterion is "beyond the limit implies an error".  It
// is FALSE, and 09-25 already contains the counterexample: at eps = +6.80%,
// past every measured limit, frame_err appeared on 8/8 bytes with data[7]=0
// and 0/8 with data[7]=1.  Beyond the tolerance limit, whether a frame
// survives depends on THE DATA -- a bit that drifts into its neighbour's
// window is only corrupted if the neighbour differs.  A coverage bin records
// that stimulus reached a region; it does not license an implication about
// what happens there.  T4 tests this as C3.
//
// PRE-REGISTERED PREDICTIONS (reported, not asserted; scored at the end)
//   C1  8E1 at eps = -3.90% -- inside the absolute "within +/-4%" bin --
//       loses at least one of 24 frames once the edge phase is randomised
//       across one oversample tick.  If so, that bin is not a safe closure
//       region for 8E1 and the item's bin definition is wrong as written.
//   C2  eps = +/-2.00% loses ZERO frames in all four configurations, 24
//       frames each.  Stated as a null prediction so that it can fail: if
//       the inner bin is not safe either, the whole banding is wrong rather
//       than just its outer edge.
//   C3  The cross cell (beyond-limit x CLEAN) is REACHABLE, so
//       "beyond the limit implies an error" cannot be an illegal bin.
//   C4  The reachability pre-pass finds exactly two unreachable cross cells,
//       both in the eps == 0 band (an exactly-nominal frame cannot produce a
//       frame error or a lost byte).
//   C5  The absolute bin edge (4.00%) and the per-configuration MEASURED
//       edge disagree about at least one probe value on at least one
//       configuration -- i.e. the two bin definitions are not
//       interchangeable on real stimulus.
//   C6  cp_baud_div, the existing coverpoint, reports the SAME single bin
//       hit across the entire eps sweep: it is provably blind to everything
//       this file measures.  Trivial to predict and worth measuring, because
//       it is the whole justification for the item.
//
// Run:  bash examples/phase6_baud_error_coverage/run_baud_cov.sh
//
// The APB and pin-driver tasks below are lifted VERBATIM from
// examples/phase6_rx_pin_driver/uart_rx_pin_tb.v.  Duplicating them is a
// real cost and is logged as an item ("factor the pin driver into an
// included file"): Icarus 10.3 here is driven as Verilog-2001 with no
// packages and no classes, so the alternatives are `include of a headerless
// fragment or this.  They are copied unchanged so that a difference in
// results between the two benches cannot be a difference in the driver.

`timescale 1ns / 1ps

module uart_baud_cov_tb;

    // -----------------------------------------------------------------
    // Clock, reset, DUT
    // -----------------------------------------------------------------
    localparam real CLK_NS = 10.0;
    localparam integer BAUD_DIV_CFG = 1;
    localparam real BIT_NS_NOM = CLK_NS * 16.0 * (BAUD_DIV_CFG + 1);   // 320 ns
    localparam real OS_TICK_NS = CLK_NS * (BAUD_DIV_CFG + 1);          // 20 ns

    reg clk = 1'b0, rst_n = 1'b0;
    always #(CLK_NS / 2.0) clk = ~clk;

    reg  [3:0] paddr = 4'h0;
    reg  [7:0] pwdata = 8'h00;
    reg        pwrite = 1'b0, psel = 1'b0, penable = 1'b0;
    wire [7:0] prdata;
    wire       pready;
    wire       tx, irq;
    reg        rx = 1'b1;

    uart_controller dut (
        .clk(clk), .rst_n(rst_n),
        .paddr(paddr), .pwdata(pwdata), .prdata(prdata),
        .pwrite(pwrite), .psel(psel), .penable(penable), .pready(pready),
        .tx(tx), .rx(rx), .irq(irq)
    );

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TXD  = 4'h3, ADDR_RXD    = 4'h4, ADDR_INTEN = 4'h5;
    localparam PAR_NONE = 2'b00, PAR_EVEN = 2'b01, PAR_ODD = 2'b10;
    localparam SB_TXFULL = 0, SB_TXEMPTY = 1, SB_RXFULL = 2, SB_RXAVAIL = 3,
               SB_FRAMEERR = 4, SB_PARERR = 5, SB_OVRERR = 6;

    integer checks = 0, errors = 0;
    reg [7:0] rd_data;

    task fail(input [8*72:1] what);
        begin
            errors = errors + 1;
            $display("  ERROR: %0s", what);
        end
    endtask

    task expect_true(input cond, input [8*64:1] what);
        begin
            checks = checks + 1;
            if (!cond) fail(what);
        end
    endtask

    // -----------------------------------------------------------------
    // APB, configuration, pin driver -- verbatim from phase6_rx_pin_driver
    // -----------------------------------------------------------------
    task apb_write(input [3:0] a, input [7:0] d);
        begin
            @(posedge clk) paddr <= a; pwdata <= d; pwrite <= 1'b1; psel <= 1'b1; penable <= 1'b0;
            @(posedge clk) penable <= 1'b1;
            @(posedge clk) psel <= 1'b0; penable <= 1'b0; pwrite <= 1'b0;
        end
    endtask

    task apb_read(input [3:0] a);
        begin
            @(posedge clk) paddr <= a; pwrite <= 1'b0; psel <= 1'b1; penable <= 1'b0;
            @(posedge clk) penable <= 1'b1;
            @(posedge clk) rd_data = prdata; psel <= 1'b0; penable <= 1'b0;
        end
    endtask

    task configure(input en, input [1:0] par, input two_stop, input lb);
        begin
            apb_write(ADDR_BAUD, BAUD_DIV_CFG[7:0]);
            apb_write(ADDR_CTRL, {3'b000, lb, two_stop, par, en});
        end
    endtask

    task clear_errors;
        begin
            apb_read(ADDR_STATUS);
            apb_read(ADDR_STATUS);
        end
    endtask

    task drive_frame(input [7:0] data, input [1:0] par, input two_stop,
                     input real drv_bit_ns, input bad_stop, input bad_par);
        integer i;
        reg p;
        begin
            rx = 1'b0;
            #(drv_bit_ns);
            for (i = 0; i < 8; i = i + 1) begin
                rx = data[i];
                #(drv_bit_ns);
            end
            if (par != PAR_NONE) begin
                p = (par == PAR_EVEN) ? ^data : ~(^data);
                rx = bad_par ? ~p : p;
                #(drv_bit_ns);
            end
            rx = bad_stop ? 1'b0 : 1'b1;
            #(drv_bit_ns);
            if (two_stop) begin
                rx = 1'b1;
                #(drv_bit_ns);
            end
            rx = 1'b1;
        end
    endtask

    task idle_gap(input real n_bits, input real drv_bit_ns);
        begin
            rx = 1'b1;
            #(n_bits * drv_bit_ns);
        end
    endtask

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

    // -----------------------------------------------------------------
    // OUTCOME CLASSIFICATION -- three-valued, because the cross needs it
    // -----------------------------------------------------------------
    // 0 CLEAN   : byte present, value correct, no sticky error bit
    // 1 ERRBIT  : a frame / parity / overrun bit is set
    // 2 LOST    : no byte at all, or a byte with the wrong value
    //
    // Distinguishing 1 from 2 is the point.  A frame that drifts off its
    // stop-bit window sets frame_err (1); a frame whose DATA bit drifts into
    // its neighbour's window and whose stop bit still lands returns a wrong
    // byte with NO error bit (2).  Those are different DUT behaviours and a
    // two-valued pass/fail oracle -- which is what recv_expect() in
    // phase6_rx_pin_driver is -- cannot tell them apart.
    localparam O_CLEAN = 0, O_ERRBIT = 1, O_LOST = 2;

    task recv_classify(input [7:0] exp, output integer code);
        reg [7:0] st;
        begin
            apb_read(ADDR_STATUS); st = rd_data;
            if (st[SB_FRAMEERR] || st[SB_PARERR] || st[SB_OVRERR])
                code = O_ERRBIT;
            else if (!st[SB_RXAVAIL])
                code = O_LOST;
            else begin
                apb_read(ADDR_RXD);
                code = (rd_data === exp) ? O_CLEAN : O_LOST;
            end
        end
    endtask

    // -----------------------------------------------------------------
    // THE COVERAGE MODEL, written out as bin counters
    // -----------------------------------------------------------------
    // Bands.  B_ZERO is eps exactly nominal; B_IN2 and B_IN4 use the
    // ABSOLUTE edges the item specified; B_BEYOND is relative to the
    // per-configuration MEASURED limit.  Keeping both kinds of edge in one
    // model is deliberate -- it is what makes their disagreement visible in
    // T2 instead of hidden in a spreadsheet.
    // FIVE bands, not the four the item named.  The fifth, B_GAP, exists
    // because the four specified bands DO NOT PARTITION THE DOMAIN: for 8N1
    // the slow limit is +6.25%, so eps = +5% is outside "within +/-4%" and
    // inside the limit, and belongs to none of {0, +/-2%, +/-4%, beyond}.
    // A closure criterion over a non-partition reports every bin hit while
    // never having sampled the 4%-to-limit region at all.  Found while
    // implementing, not predicted; see the report.
    localparam B_ZERO = 0, B_IN2 = 1, B_IN4 = 2, B_GAP = 3, B_BEYOND = 4;
    localparam N_BAND = 5, N_CFG = 4, N_OUT = 3;

    integer cov_band  [0:4];
    integer cov_cfg   [0:3];
    integer cov_cross [0:14];       // band*3 + outcome, flattened for Icarus
    integer cov_bauddiv [0:3];      // the OLD coverpoint, kept for C6

    // THREE verdicts, not two.  The first run of this bench had two -- a cell
    // was "reachable" if the pre-pass produced it and "unreachable"
    // otherwise, and every unreachable cell became an illegal bin.  Twenty-one
    // frames into the random closure run, one of those illegal bins FIRED on
    // perfectly legal DUT behaviour (B3 x ERRBIT: an eps just inside the
    // measured limit, with a data pattern and edge phase the pre-pass had not
    // tried).  A pre-pass answers "did my attempts reach it", which is not
    // "is it reachable", and collapsing the two manufactures false failures.
    //   CLS_OPEN     0  not reached by the pre-pass, and not ruled out
    //   CLS_REACHED  1  produced by the pre-pass
    //   CLS_EXCLUDED 2  excluded BY ARGUMENT, not by failure to reach
    // Only CLS_EXCLUDED becomes an illegal bin.  CLS_OPEN is neither a
    // coverage goal nor an assertion -- it is an honest "don't know", which
    // is what a coverage report owes a bin it can neither hit nor rule out.
    localparam CLS_OPEN = 0, CLS_REACHED = 1, CLS_EXCLUDED = 2;
    integer cls [0:14];
    integer prepass_done = 0;

    task cov_reset;
        integer i;
        begin
            for (i = 0; i < N_BAND; i = i + 1) cov_band[i] = 0;
            for (i = 0; i < N_CFG;  i = i + 1) cov_cfg[i]  = 0;
            for (i = 0; i < 15;     i = i + 1) cov_cross[i] = 0;
            for (i = 0; i < 4;      i = i + 1) cov_bauddiv[i] = 0;
            for (i = 0; i < 15;     i = i + 1) cls[i] = CLS_OPEN;
        end
    endtask

    // Sampling is a single task called at exactly one place per frame, so a
    // bin cannot be updated on a path that skipped the check -- the bug
    // 09-24 recorded as "the closure criterion and the counter disagreed
    // about which frames existed".
    task cov_sample(input integer band, input integer cfg, input integer code);
        begin
            cov_band[band]  = cov_band[band]  + 1;
            cov_cfg[cfg]    = cov_cfg[cfg]    + 1;
            cov_cross[band * N_OUT + code] = cov_cross[band * N_OUT + code] + 1;
            // the old coverpoint, sampled from the register the way it always was
            if      (BAUD_DIV_CFG == 0)   cov_bauddiv[0] = cov_bauddiv[0] + 1;
            else if (BAUD_DIV_CFG == 255) cov_bauddiv[3] = cov_bauddiv[3] + 1;
            else if (BAUD_DIV_CFG < 128)  cov_bauddiv[1] = cov_bauddiv[1] + 1;
            else                          cov_bauddiv[2] = cov_bauddiv[2] + 1;
        end
    endtask

    // -----------------------------------------------------------------
    // Configurations and measured limits
    // -----------------------------------------------------------------
    // cfg: 0 = 8N1, 1 = 8N2, 2 = 8E1, 3 = 8O1
    function [1:0] cfg_par(input integer c);
        cfg_par = (c == 2) ? PAR_EVEN : (c == 3) ? PAR_ODD : PAR_NONE;
    endfunction
    function cfg_two_stop(input integer c);
        cfg_two_stop = (c == 1);
    endfunction

    integer lim_fast_bp [0:3];      // magnitude, basis points (1 bp = 0.01%)
    integer lim_slow_bp [0:3];

    // eps is carried in basis points throughout, as in phase6_rx_pin_driver.
    localparam integer EPS_STEP_BP = 25;      // coarser than 09-25's 5 bp
    localparam integer EPS_MAX_BP  = 900;
    localparam integer FRAMES_PER_TRIAL = 6;   // 09-25 used 6; see T0b

    reg [7:0] pat [0:5];
    reg [7:0] alt [0:5];
    integer seed = 1;
    integer phase_seed = 7;

    // A frame driven with a randomised edge phase.  The DUT's oversample
    // counter free-runs, so the phase of the arriving edge within one
    // oversample tick is uncontrolled in the field and uncontrolled here;
    // sweeping it is the only way to see the BAND that 09-25 could only
    // infer.  One tick is 20 ns at BAUD_DIV=1, and the driver's timescale is
    // 1 ns, so 20 distinct phases exist.
    task drive_phased(input [7:0] data, input integer cfg,
                      input real drv_bit_ns, input integer phase_ns);
        begin
            #(phase_ns * 1.0);
            drive_frame(data, cfg_par(cfg), cfg_two_stop(cfg), drv_bit_ns,
                        1'b0, 1'b0);
        end
    endtask

    function real bit_ns_of(input integer eps_bp);
        bit_ns_of = BIT_NS_NOM * (1.0 + eps_bp / 10000.0);
    endfunction

    // =================================================================
    // T0 -- measure each configuration's limit, so the BEYOND band has an
    //       edge that belongs to this DUT rather than to a document
    // =================================================================
    task measure_limit(input integer cfg, input integer sgn, input integer n_pat,
                       input use_alt, output integer tol_bp);
        integer e, f;
        integer code;
        reg all_ok;
        reg [7:0] tb;
        real bns;
        begin
            configure(1'b1, cfg_par(cfg), cfg_two_stop(cfg), 1'b0);
            tol_bp = -1;
            e = 0;
            all_ok = 1'b1;
            while (all_ok && e <= EPS_MAX_BP) begin
                bns = bit_ns_of(sgn * e);
                drain;
                all_ok = 1'b1;
                for (f = 0; f < n_pat; f = f + 1) begin
                    tb = use_alt ? alt[f] : pat[f];
                    drive_frame(tb, cfg_par(cfg), cfg_two_stop(cfg),
                                bns, 1'b0, 1'b0);
                    idle_gap(3.0, bns);
                    recv_classify(tb, code);
                    if (code != O_CLEAN) all_ok = 1'b0;
                    clear_errors;
                end
                if (all_ok) begin
                    tol_bp = e;
                    e = e + EPS_STEP_BP;
                end
            end
        end
    endtask

    // 09-25's measured phase sensitivity: one oversample tick of uncontrolled
    // edge phase moves each limit by 0.69% of eps.  Used as the derived
    // tolerance of the cross-check below -- not as a fudge factor, which is
    // why it is named and sourced.
    localparam integer PHASE_BAND_BP = 69;

    function near_0925(input integer meas, input integer ref_bp);
        near_0925 = (meas >= ref_bp - PHASE_BAND_BP - EPS_STEP_BP)
                 && (meas <= ref_bp + PHASE_BAND_BP);
    endfunction

    integer lim_fast_4pat [0:3];
    integer pat_gap_max_bp = 0;

    task t0_measure_limits;
        integer c, d;
        begin
            $display("");
            $display("--- T0: per-configuration limits, re-measured here (%0d bp steps, %0d patterns) ---",
                     EPS_STEP_BP, FRAMES_PER_TRIAL);
            for (c = 0; c < N_CFG; c = c + 1) begin
                measure_limit(c, -1, FRAMES_PER_TRIAL, 1'b0, lim_fast_bp[c]);
                measure_limit(c, +1, FRAMES_PER_TRIAL, 1'b0, lim_slow_bp[c]);
            end
            $display("  cfg     fast      slow     09-25 reference (5 bp, 6 patterns)");
            $display("  8N1   -%0d.%02d%%   +%0d.%02d%%    -4.50%% / +6.25%%",
                     lim_fast_bp[0]/100, lim_fast_bp[0]%100,
                     lim_slow_bp[0]/100, lim_slow_bp[0]%100);
            $display("  8N2   -%0d.%02d%%   +%0d.%02d%%    -4.50%% / +6.25%%",
                     lim_fast_bp[1]/100, lim_fast_bp[1]%100,
                     lim_slow_bp[1]/100, lim_slow_bp[1]%100);
            $display("  8E1   -%0d.%02d%%   +%0d.%02d%%    -4.05%% / +5.60%%",
                     lim_fast_bp[2]/100, lim_fast_bp[2]%100,
                     lim_slow_bp[2]/100, lim_slow_bp[2]%100);
            $display("  8O1   -%0d.%02d%%   +%0d.%02d%%    -4.05%% / +5.60%%",
                     lim_fast_bp[3]/100, lim_fast_bp[3]%100,
                     lim_slow_bp[3]/100, lim_slow_bp[3]%100);
            $display("  ANCHORED CROSS-CHECK against 09-25, and the TOLERANCE OF THAT");
            $display("  CHECK IS DERIVED, not chosen.  Two effects separate the two");
            $display("  benches: the %0d bp grid (this sweep reports the largest multiple",
                     EPS_STEP_BP);
            $display("  of %0d at or below the limit) and the uncontrolled start-up phase",
                     EPS_STEP_BP);
            $display("  between the driver's timebase and the DUT's free-running");
            $display("  oversample counter, which 09-25 measured as moving each limit by");
            $display("  %0d bp.  So the window is 09-25's value -%0d-%0d bp .. +%0d bp:",
                     PHASE_BAND_BP, PHASE_BAND_BP, EPS_STEP_BP, PHASE_BAND_BP);
            expect_true(near_0925(lim_fast_bp[0], 450),
                        "8N1 fast limit outside 09-25 +/- the phase band");
            expect_true(near_0925(lim_slow_bp[0], 625),
                        "8N1 slow limit outside 09-25 +/- the phase band");
            expect_true(near_0925(lim_fast_bp[2], 405),
                        "8E1 fast limit outside 09-25 +/- the phase band");
            expect_true(near_0925(lim_slow_bp[2], 560),
                        "8E1 slow limit outside 09-25 +/- the phase band");
            expect_true(lim_fast_bp[2] < lim_fast_bp[0],
                        "parity should tighten the fast limit (09-25 P2)");
            $display("  measured spread vs 09-25: 8N1 fast %0s%0d bp, 8E1 fast %0s%0d bp.",
                     (lim_fast_bp[0]>=450)?"+":"-",
                     (lim_fast_bp[0]>=450)?(lim_fast_bp[0]-450):(450-lim_fast_bp[0]),
                     (lim_fast_bp[2]>=405)?"+":"-",
                     (lim_fast_bp[2]>=405)?(lim_fast_bp[2]-405):(405-lim_fast_bp[2]));
            $display("  An independent bench landing inside that window rather than ON the");
            $display("  number is 09-25's 'quote it as a band' CONFIRMED by a second");
            $display("  measurement instead of inferred from the sampling geometry.");
        end
    endtask

    // T0b -- A MEASURED TOLERANCE IS AS TIGHT AS THE BYTES THAT MEASURED IT.
    // Found by the anchored cross-check above FAILING on the first run of
    // this bench, which used the same NUMBER of trial bytes as 09-25 (six)
    // with two of them different -- 0x3C and 0x81 in place of 0x01 and 0x80 --
    // and reported limits up to 0.70% of eps WIDER.  Same DUT, same sweep,
    // same trial size, different answer.  The BEYOND band's edge is derived
    // from this number, so the bin edge inherits the optimism of whichever
    // bytes happened to be in the trial set: a coverage bin whose boundary is
    // measured is a claim about the measuring stimulus as much as about the
    // DUT.  Kept as a standing experiment rather than a paragraph, because it
    // is cheap and it is the reason the cross-check exists at all.
    task t0b_pattern_dependence;
        integer c, d;
        begin
            $display("");
            $display("--- T0b: the same limit, measured with two trial bytes swapped ---");
            $display("  trial set A (09-25's): 00 FF AA 55 01 80");
            $display("  trial set B (this one): 00 FF AA 55 3C 81");
            $display("  cfg   fast(set A)   fast(set B)   difference");
            pat_gap_max_bp = 0;
            for (c = 0; c < N_CFG; c = c + 1) begin
                measure_limit(c, -1, FRAMES_PER_TRIAL, 1'b1, lim_fast_4pat[c]);
                d = lim_fast_4pat[c] - lim_fast_bp[c];
                if (d > pat_gap_max_bp) pat_gap_max_bp = d;
                $display("  %0d      -%0d.%02d%%       -%0d.%02d%%       %0s%0d.%02d%%",
                         c, lim_fast_bp[c]/100, lim_fast_bp[c]%100,
                         lim_fast_4pat[c]/100, lim_fast_4pat[c]%100,
                         (d >= 0) ? "+" : "-", (d<0?-d:d)/100, (d<0?-d:d)%100);
            end
            $display("  worst shift from swapping two of six trial bytes: %0d.%02d%% of eps",
                     pat_gap_max_bp/100, pat_gap_max_bp%100);
            $display("  0x01 and 0x80 put a lone 1 at each END of the byte, adjacent to");
            $display("  the start and stop bits -- exactly where a drifting sample lands");
            $display("  on a DIFFERING neighbour.  0x3C and 0x81 do not.  A tolerance");
            $display("  measured without those two is not a noisier measurement of the");
            $display("  same quantity; it is a measurement of a different one, and it is");
            $display("  OPTIMISTIC, which is the direction that matters for a bin edge.");
            expect_true(pat_gap_max_bp > 0,
                        "swapping the end-bit bytes should widen the measured limit");
        end
    endtask

    // Refine each limit to the 5 bp grid 09-25 used, by stepping from the
    // coarse answer.  Without this, the "measured edge" and the absolute
    // 4.00% edge coincide at 8E1 purely because of the 25 bp grid -- a
    // measurement artefact masquerading as agreement.
    task refine_limit(input integer cfg, input integer sgn, input integer n_pat,
                      inout integer tol_bp);
        integer e, f, code;
        reg all_ok;
        real bns;
        begin
            configure(1'b1, cfg_par(cfg), cfg_two_stop(cfg), 1'b0);
            e = tol_bp + 5;
            all_ok = 1'b1;
            while (all_ok && e < tol_bp + EPS_STEP_BP + 5) begin
                bns = bit_ns_of(sgn * e);
                drain;
                all_ok = 1'b1;
                for (f = 0; f < n_pat; f = f + 1) begin
                    drive_frame(pat[f], cfg_par(cfg), cfg_two_stop(cfg),
                                bns, 1'b0, 1'b0);
                    idle_gap(3.0, bns);
                    recv_classify(pat[f], code);
                    if (code != O_CLEAN) all_ok = 1'b0;
                    clear_errors;
                end
                if (all_ok) begin tol_bp = e; e = e + 5; end
            end
        end
    endtask

    task t0c_refine;
        integer c;
        begin
            for (c = 0; c < N_CFG; c = c + 1) begin
                refine_limit(c, -1, FRAMES_PER_TRIAL, lim_fast_bp[c]);
                refine_limit(c, +1, FRAMES_PER_TRIAL, lim_slow_bp[c]);
            end
            $display("  refined to the 5 bp grid:  8N1 -%0d.%02d%%/+%0d.%02d%%   8E1 -%0d.%02d%%/+%0d.%02d%%",
                     lim_fast_bp[0]/100, lim_fast_bp[0]%100,
                     lim_slow_bp[0]/100, lim_slow_bp[0]%100,
                     lim_fast_bp[2]/100, lim_fast_bp[2]%100,
                     lim_slow_bp[2]/100, lim_slow_bp[2]%100);
        end
    endtask

    // Band of a signed eps, for a given configuration.
    function integer band_of(input integer eps_bp, input integer cfg);
        integer m, lim;
        begin
            m = (eps_bp < 0) ? -eps_bp : eps_bp;
            lim = (eps_bp < 0) ? lim_fast_bp[cfg] : lim_slow_bp[cfg];
            if      (eps_bp == 0) band_of = B_ZERO;
            else if (m <= 200)    band_of = B_IN2;
            else if (m <= 400)    band_of = B_IN4;
            else if (m <= lim)    band_of = B_GAP;
            else                  band_of = B_BEYOND;
        end
    endfunction

    integer c5_disagreements = 0;
    integer c6_bauddiv_hits = 0;

    // =================================================================
    // T1 -- C6: the existing coverpoint is blind to all of this
    // =================================================================
    task t1_old_coverpoint_is_blind;
        integer c, code, e, i, hits;
        real bns;
        begin
            $display("");
            $display("--- T1: what cp_baud_div sees while eps sweeps its whole range (C6) ---");
            for (i = 0; i < 4; i = i + 1) cov_bauddiv[i] = 0;
            c = 0;
            configure(1'b1, cfg_par(c), cfg_two_stop(c), 1'b0);
            for (e = -800; e <= 800; e = e + 200) begin
                bns = bit_ns_of(e);
                drain;
                drive_frame(8'hA5, cfg_par(c), cfg_two_stop(c), bns, 1'b0, 1'b0);
                idle_gap(3.0, bns);
                recv_classify(8'hA5, code);
                cov_sample(band_of(e, c), c, code);
                clear_errors;
            end
            hits = 0;
            for (i = 0; i < 4; i = i + 1) if (cov_bauddiv[i] > 0) hits = hits + 1;
            $display("  eps swept -8.00%% .. +8.00%%; cp_baud_div bins hit: %0d of 4", hits);
            $display("  cp_baud_div samples the DIVISOR REGISTER, which never changed.");
            $display("  A coverage report built on it reads 'covered' across a sweep");
            $display("  that takes the receiver from perfect to broken and back.");
            expect_true(hits == 1, "cp_baud_div should see exactly one bin here");
            c6_bauddiv_hits = hits;
        end
    endtask

    // =================================================================
    // T2 -- C5: absolute bin edge vs measured edge, on real probe values
    // =================================================================
    task t2_edge_disagreement;
        integer c, e, abs_in, meas_in;
        begin
            $display("");
            $display("--- T2: absolute bin edge (4.00%%) vs measured limit (C5) ---");
            $display("  cfg   eps      'within +/-4%%'?   inside measured limit?   agree?");
            for (c = 0; c < N_CFG; c = c + 1) begin
                for (e = 395; e <= 415; e = e + 10) begin
                    abs_in  = (e <= 400);
                    meas_in = (e <= lim_fast_bp[c]);
                    if (abs_in != meas_in) c5_disagreements = c5_disagreements + 1;
                    $display("  %0d    -%0d.%02d%%        %0s                 %0s              %0s",
                             c, e/100, e%100,
                             abs_in ? "yes" : "no ", meas_in ? "yes" : "no ",
                             (abs_in == meas_in) ? "yes" : "NO");
                end
            end
            $display("  disagreements: %0d", c5_disagreements);
            $display("  An absolute bin edge on a tolerance is a claim about scale.");
            $display("  Where the two columns differ, a closure report over the");
            $display("  absolute bins describes a region the DUT does not have.");
        end
    endtask

    // =================================================================
    // T3 -- C1 and C2: is a band SAFE once the edge phase is randomised?
    // =================================================================
    integer c1_losses = 0, c2_losses = 0, c1_beyond_clean = 0;
    localparam integer PHASE_FRAMES = 24;

    task phase_probe(input integer cfg, input integer eps_bp,
                     output integer n_bad, output integer n_clean);
        integer i, code, ph;
        reg [7:0] d;
        real bns;
        begin
            configure(1'b1, cfg_par(cfg), cfg_two_stop(cfg), 1'b0);
            bns = bit_ns_of(eps_bp);
            n_bad = 0; n_clean = 0;
            for (i = 0; i < PHASE_FRAMES; i = i + 1) begin
                ph = {$random(phase_seed)} % 20;      // one oversample tick
                d  = pat[i % 6];
                drain;
                drive_phased(d, cfg, bns, ph);
                idle_gap(3.0, bns);
                recv_classify(d, code);
                cov_sample(band_of(eps_bp, cfg), cfg, code);
                if (code == O_CLEAN) n_clean = n_clean + 1; else n_bad = n_bad + 1;
                clear_errors;
            end
        end
    endtask

    task t3_phase_probes;
        integer c, nb, nc, tot;
        begin
            $display("");
            $display("--- T3: is a band safe once the edge phase is randomised? (C1, C2) ---");
            $display("  %0d frames per point, edge phase uniform over one oversample tick (20 ns)",
                     PHASE_FRAMES);
            $display("  C2, the inner band:");
            tot = 0;
            for (c = 0; c < N_CFG; c = c + 1) begin
                phase_probe(c, +200, nb, nc);
                tot = tot + nb;
                $display("    cfg %0d  eps = +2.00%%   clean %0d/%0d   lost %0d",
                         c, nc, PHASE_FRAMES, nb);
                phase_probe(c, -200, nb, nc);
                tot = tot + nb;
                $display("    cfg %0d  eps = -2.00%%   clean %0d/%0d   lost %0d",
                         c, nc, PHASE_FRAMES, nb);
            end
            c2_losses = tot;
            $display("  C1, 8E1 just inside the absolute +/-4%% bin:");
            phase_probe(2, -390, nb, nc);
            c1_losses = nb;
            $display("    8E1    eps = -3.90%%   clean %0d/%0d   lost %0d   (measured limit -%0d.%02d%%)",
                     nc, PHASE_FRAMES, nb, lim_fast_bp[2]/100, lim_fast_bp[2]%100);
            phase_probe(2, -430, nb, nc);
            c1_beyond_clean = nc;
            $display("    8E1    eps = -4.30%%   clean %0d/%0d   lost %0d   (past the measured limit)",
                     nc, PHASE_FRAMES, nb);
            $display("  The second row is the interesting one either way: a nonzero");
            $display("  clean count past the measured limit means the limit is a band");
            $display("  in the phase variable, which is what 09-25 could only infer.");
        end
    endtask

    // =================================================================
    // T4 -- THE REACHABILITY PRE-PASS
    // =================================================================
    // 09-24's finding 9, applied: establish that a cell CAN be produced
    // before any closure criterion depends on it.  Every cell is attempted
    // with stimulus aimed at it.
    //
    // THE STIMULUS SPACE IS PART OF THE ANSWER, and naming it is the point.
    // This pre-pass varies eps, data, edge phase and configuration, and
    // drives only WELL-FORMED frames.  Within that space an eps == 0 frame
    // cannot produce a frame error.  In the FULL stimulus space it obviously
    // can -- corrupt the stop bit -- which t4b demonstrates deliberately.
    // So "unreachable" is never a property of a bin; it is a property of a
    // bin AND a stimulus space, and a coverage model that does not name its
    // space cannot say what an unhit bin means.
    integer attempted = 0;
    integer n_reachable = 0, n_unreachable = 0, n_excluded = 0;

    task attempt(input integer cfg, input integer eps_bp, input [7:0] d,
                 input integer ph);
        integer code, b;
        real bns;
        begin
            configure(1'b1, cfg_par(cfg), cfg_two_stop(cfg), 1'b0);
            bns = bit_ns_of(eps_bp);
            drain;
            drive_phased(d, cfg, bns, ph);
            idle_gap(3.0, bns);
            recv_classify(d, code);
            b = band_of(eps_bp, cfg);
            if (cls[b * N_OUT + code] == CLS_EXCLUDED)
                fail("pre-pass produced a cell argued to be excluded");
            cls[b * N_OUT + code] = CLS_REACHED;
            attempted = attempted + 1;
            clear_errors;
        end
    endtask

    function [8*8:1] cname(input integer v);
        cname = (v == CLS_REACHED) ? "REACHED " :
                (v == CLS_EXCLUDED) ? "EXCLUDED" : "  open  ";
    endfunction

    task t4_reachability_prepass;
        integer c, i, b, o, n_reach, n_unreach, n_excl;
        integer e;
        begin
            $display("");
            $display("--- T4: reachability pre-pass over all %0d cross cells ---",
                     N_BAND * N_OUT);
            $display("  stimulus space: well-formed frames; eps, data, edge phase, config");
            // EXCLUDED BY ARGUMENT, before any stimulus runs.  At eps == 0 the
            // driver's bit period equals the DUT's nominal period exactly, so
            // no drift accumulates over a frame; the only free variable is the
            // initial edge phase, which moves every sample point by less than
            // one oversample tick (1/16 bit) against a half-bit margin.  A
            // well-formed frame therefore cannot lose a bit or miss its stop
            // bit.  That is an argument about the mechanism; the pre-pass's
            // attempts below are a necessary check on it, not its basis.
            cls[B_ZERO*N_OUT + O_ERRBIT] = CLS_EXCLUDED;
            cls[B_ZERO*N_OUT + O_LOST]   = CLS_EXCLUDED;
            for (c = 0; c < N_CFG; c = c + 1) begin
                // B_ZERO
                attempt(c, 0, 8'h00, 0);
                attempt(c, 0, 8'hFF, 7);
                attempt(c, 0, 8'hAA, 13);
                // B_IN2 both signs
                attempt(c, +150, 8'h55, 3);
                attempt(c, -150, 8'hAA, 11);
                // B_IN4 both signs
                attempt(c, +350, 8'h0F, 5);
                attempt(c, -350, 8'hF0, 17);
                attempt(c, -395, 8'hAA, 9);
                attempt(c, +395, 8'h55, 14);
                // B_GAP: above 4% and inside the measured limit (slow side
                // always has room; fast side only if the limit exceeds 400)
                if (lim_slow_bp[c] > 425) attempt(c, +425, 8'hAA, 2);
                if (lim_slow_bp[c] > 500) attempt(c, +500, 8'h5A, 19);
                if (lim_fast_bp[c] > 425) attempt(c, -425, 8'hA5, 6);
                // aimed squarely at the cell the first version of this bench
                // wrongly called unreachable: just inside the measured limit,
                // with the pattern and phases that can actually break there
                attempt(c, lim_slow_bp[c] - 5,  8'hAA, 0);
                attempt(c, lim_slow_bp[c] - 5,  8'hAA, 10);
                attempt(c, -(lim_fast_bp[c] - 5), 8'hAA, 0);
                attempt(c, -(lim_fast_bp[c] - 5), 8'hAA, 10);
                // B_BEYOND: several data patterns, because C3 says the
                // outcome there is DATA-dependent
                e = lim_slow_bp[c] + 75;
                attempt(c, e, 8'hAA, 4);        // alternating: drifts into a differing neighbour
                attempt(c, e, 8'hFF, 8);        // all ones: nothing to corrupt
                attempt(c, e, 8'h00, 12);
                attempt(c, e + 200, 8'hAA, 16);
                e = -(lim_fast_bp[c] + 75);
                attempt(c, e, 8'hAA, 1);
                attempt(c, e, 8'h00, 15);
                attempt(c, e - 200, 8'hAA, 10);
            end
            n_reach = 0; n_unreach = 0; n_excl = 0;
            $display("  band \\ outcome         CLEAN    ERRBIT     LOST");
            for (b = 0; b < N_BAND; b = b + 1) begin
                $display("  %0s   %0s   %0s   %0s",
                         (b==B_ZERO) ? "B0 eps==0      " :
                         (b==B_IN2)  ? "B1 |eps|<=2%   " :
                         (b==B_IN4)  ? "B2 2%<|eps|<=4%" :
                         (b==B_GAP)  ? "B3 4%<|eps|<=L " : "B4 |eps|>L     ",
                         cname(cls[b*N_OUT+0]), cname(cls[b*N_OUT+1]),
                         cname(cls[b*N_OUT+2]));
                for (o = 0; o < N_OUT; o = o + 1)
                    if      (cls[b*N_OUT+o] == CLS_REACHED)  n_reach = n_reach + 1;
                    else if (cls[b*N_OUT+o] == CLS_EXCLUDED) n_excl  = n_excl + 1;
                    else                                     n_unreach = n_unreach + 1;
            end
            $display("  %0d frames attempted; %0d REACHED, %0d EXCLUDED by argument, %0d OPEN",
                     attempted, n_reach, n_excl, n_unreach);
            $display("  Only the %0d EXCLUDED cells become illegal bins. The %0d OPEN cells",
                     n_excl, n_unreach);
            $display("  are carried as unknown: not in the closure criterion, not asserted.");
            n_reachable = n_reach;
            n_unreachable = n_unreach;
            n_excluded = n_excl;
            for (i = 0; i < 15; i = i + 1)
                prepass_reached[i] = (cls[i] == CLS_REACHED);
            prepass_done = 1;
        end
    endtask

    // t4b -- the same bin, a WIDER stimulus space, a different verdict.
    // Deliberately OUTSIDE the pre-pass's space and excluded from reach[].
    integer t4b_code = -1;
    task t4b_space_matters;
        integer code;
        begin
            $display("");
            $display("--- T4b: 'unreachable' is a property of the STIMULUS SPACE ---");
            configure(1'b1, PAR_NONE, 1'b0, 1'b0);
            drain;
            drive_frame(8'h3C, PAR_NONE, 1'b0, BIT_NS_NOM, 1'b1, 1'b0); // bad stop
            idle_gap(3.0, BIT_NS_NOM);
            recv_classify(8'h3C, code);
            t4b_code = code;
            $display("  eps == 0 exactly, stop bit driven LOW -> outcome %0s",
                     (code==O_CLEAN) ? "CLEAN" : (code==O_ERRBIT) ? "ERRBIT" : "LOST");
            $display("  So (B0 x ERRBIT) is reachable in the full space and not in the");
            $display("  pre-pass's.  Neither verdict is wrong; a report that omits the");
            $display("  space is.  This frame is NOT recorded in cls[] or in coverage.");
            expect_true(code == O_ERRBIT,
                        "a low stop bit at eps==0 should raise frame_err");
        end
    endtask

    // =================================================================
    // T5 -- CLOSURE, over the reachable cells only
    // =================================================================
    integer closure_frames = -1;
    integer illegal_hits = 0;
    integer refutations = 0;
    integer closure_target = 0;

    integer tgt [0:14];
    integer prepass_reached [0:14];
    integer close_random = -1, close_steered = -1;
    integer ref_before = 0;

    task t5_closure(input integer budget, input steered, output integer frames_to_close);
        integer i, c, e, ph, b, o, code, hit, sgn, pick, aim;
        reg [7:0] d;
        real bns;
        begin
            $display("");
            $display("--- T5%0s: closure over the %0d cells the pre-pass REACHED (budget %0d) ---",
                     steered ? "b, coverage-DRIVEN" : "a, pure random", n_reachable, budget);
            for (i = 0; i < 15; i = i + 1) cov_cross[i] = 0;
            for (i = 0; i < N_BAND; i = i + 1) cov_band[i] = 0;
            // snapshot: closure is judged against what the PRE-PASS reached,
            // so a cell the random run refutes later cannot move the goalpost
            closure_target = n_reachable;
            ref_before = refutations;
            for (i = 0; i < 15; i = i + 1) tgt[i] = prepass_reached[i];
            closure_frames = -1;
            i = 0;
            while (i < budget && closure_frames < 0) begin
                c = {$random(seed)} % N_CFG;
                sgn = ({$random(seed)} % 2) ? 1 : -1;
                d  = $random(seed);
                ph = {$random(seed)} % 20;
                // COVERAGE-DRIVEN STEERING (steered=1): find the first target
                // cell still unhit and aim this frame's band at it, exactly as
                // examples/phase6_crv_uart's generator aims at its first unhit
                // bin.  A cell that only occurs in the last few basis points
                // below a limit has a vanishing chance under a uniform draw;
                // steering is what turns "reachable" into "reached".
                aim = -1;
                if (steered)
                    for (b = N_BAND-1; b >= 0; b = b - 1)
                        for (o = 0; o < N_OUT; o = o + 1)
                            if (tgt[b*N_OUT+o] && cov_cross[b*N_OUT+o] == 0) aim = b;
                if (aim >= 0) begin
                    pick = aim;
                    d = 8'hAA;          // adjacent bits differ everywhere
                end
                else pick = {$random(seed)} % 5;
                case (pick)
                  0: e = 0;
                  1: e = sgn * (({$random(seed)} % 200) + 1);
                  2: e = sgn * (({$random(seed)} % 200) + 201);
                  // Unsteered, B3 is drawn UNIFORMLY over 4.05%..5.55%, which
                  // is the natural first choice and the reason T5a exists:
                  // the ERRBIT outcome lives in the last few basis points
                  // below the limit and a uniform draw almost never lands
                  // there.  Steered, the draw is aimed at the boundary.
                  3: e = (aim == 3)
                         ? ((sgn < 0) ? -(lim_fast_bp[c] - ({$random(seed)} % 15))
                                      :  (lim_slow_bp[c] - ({$random(seed)} % 15)))
                         : sgn * (({$random(seed)} % 150) + 405);
                  default: e = sgn * (((sgn<0) ? lim_fast_bp[c] : lim_slow_bp[c])
                                      + 50 + ({$random(seed)} % 250));
                endcase
                if (pick == 3 && ((sgn<0 ? lim_fast_bp[c] : lim_slow_bp[c]) <= 400))
                    e = sgn * 350;      // no B3 region exists for this config
                configure(1'b1, cfg_par(c), cfg_two_stop(c), 1'b0);
                bns = bit_ns_of(e);
                drain;
                drive_phased(d, c, bns, ph);
                idle_gap(3.0, bns);
                recv_classify(d, code);
                b = band_of(e, c);
                cov_sample(b, c, code);
                // ILLEGAL-BIN CHECK: a cell the pre-pass proved unreachable
                // must not appear here.  This is the half of the model that
                // is an assertion rather than a coverage goal -- coverage
                // says "we tried", an illegal bin says "this must not
                // happen", and a tolerance claim belongs in the second.
                if (cls[b*N_OUT+code] == CLS_EXCLUDED) begin
                    illegal_hits = illegal_hits + 1;
                    fail("closure run hit a cell EXCLUDED by argument");
                end
                else if (cls[b*N_OUT+code] == CLS_OPEN) begin
                    // The random run reached what the pre-pass could not.
                    // This is a RESULT, not an error: it is the measured rate
                    // at which a directed pre-pass under-reports reachability.
                    refutations = refutations + 1;
                    cls[b*N_OUT+code] = CLS_REACHED;
                    $display("    refuted: band %0d x outcome %0d reached at frame %0d (eps=%0d bp, cfg %0d)",
                             b, code, i, e, c);
                end
                clear_errors;
                i = i + 1;
                hit = 1;
                for (b = 0; b < N_BAND; b = b + 1)
                    for (o = 0; o < N_OUT; o = o + 1)
                        if (tgt[b*N_OUT+o] && cov_cross[b*N_OUT+o] == 0) hit = 0;
                if (hit) closure_frames = i;
            end
            frames_to_close = closure_frames;
            if (closure_frames >= 0)
                $display("  CLOSED after %0d frames", closure_frames);
            else begin
                $display("  NOT CLOSED in %0d frames; unhit reachable cells:", budget);
                for (b = 0; b < N_BAND; b = b + 1)
                    for (o = 0; o < N_OUT; o = o + 1)
                        if (tgt[b*N_OUT+o] && cov_cross[b*N_OUT+o] == 0)
                            $display("    band %0d x outcome %0d", b, o);
            end
            $display("  illegal-bin hits: %0d (must be 0)", illegal_hits);
            $display("  cells this pass refuted (reached though the pre-pass had not): %0d",
                     refutations - ref_before);
            $display("  cumulative refutations: %0d -- the measured rate at which a",
                     refutations);
            $display("  directed pre-pass under-reports reachability.");
            expect_true(illegal_hits == 0, "an EXCLUDED cross cell was hit");
        end
    endtask

    // =================================================================
    // Report and scoring
    // =================================================================
    task report;
        integer b, o, i, bhit;
        begin
            $display("");
            $display("--- COVERAGE REPORT (closure run) ---");
            $display("  band                    frames   CLEAN  ERRBIT   LOST");
            for (b = 0; b < N_BAND; b = b + 1)
                $display("  %0s      %4d    %4d    %4d   %4d",
                         (b==B_ZERO) ? "B0 eps==0      " :
                         (b==B_IN2)  ? "B1 |eps|<=2%   " :
                         (b==B_IN4)  ? "B2 2%<|eps|<=4%" :
                         (b==B_GAP)  ? "B3 4%<|eps|<=L " : "B4 |eps|>L     ",
                         cov_band[b], cov_cross[b*N_OUT+0],
                         cov_cross[b*N_OUT+1], cov_cross[b*N_OUT+2]);
            bhit = 0;
            for (i = 0; i < N_BAND*N_OUT; i = i + 1) if (cov_cross[i] > 0) bhit = bhit + 1;
            $display("  cross cells hit: %0d of %0d total; the pre-pass had reached %0d",
                     bhit, N_BAND*N_OUT, closure_target);

            $display("");
            $display("--- PRE-REGISTERED PREDICTIONS, SCORED ---");
            $display("  C1 8E1 at -3.90%% loses >=1 of %0d with random phase    %0s  (lost %0d)",
                     PHASE_FRAMES, (c1_losses >= 1) ? "PASS" : "FAIL", c1_losses);
            $display("  C2 eps = +/-2.00%% loses ZERO frames, all configs      %0s  (lost %0d)",
                     (c2_losses == 0) ? "PASS" : "FAIL", c2_losses);
            $display("  C3 (beyond-limit x CLEAN) is REACHABLE                %0s",
                     (cls[B_BEYOND*N_OUT+O_CLEAN] == CLS_REACHED) ? "PASS" : "FAIL");
            $display("  C4 exactly 2 non-reachable cells, both in B0          %0s  (%0d open + %0d excluded)",
                     ((n_unreachable + n_excluded) == 2) ? "PASS" : "FAIL",
                     n_unreachable, n_excluded);
            $display("  C5 absolute and measured edges disagree somewhere     %0s  (%0d rows)",
                     (c5_disagreements > 0) ? "PASS" : "FAIL", c5_disagreements);
            $display("  C6 cp_baud_div hits one bin across the whole sweep    %0s  (%0d bins)",
                     (c6_bauddiv_hits == 1) ? "PASS" : "FAIL", c6_bauddiv_hits);
            $display("  Predictions are REPORTED, not asserted: a wrong prediction about");
            $display("  the DUT is a result, and failing the run on one would hide it.");

            $display("");
            $display("--- FOUND WHILE IMPLEMENTING (not pre-registered) ---");
            $display("  The four bands the item specified -- {0, +/-2%%, +/-4%%, beyond the");
            $display("  limit} -- DO NOT PARTITION eps.  For 8N1 the slow limit is");
            $display("  +%0d.%02d%%, so eps = +5.00%% is outside 'within +/-4%%' and inside",
                     lim_slow_bp[0]/100, lim_slow_bp[0]%100);
            $display("  the limit, belonging to no band.  B3 exists to hold that region;");
            $display("  it took %0d frames of the closure run, which a four-band model",
                     cov_band[B_GAP]);
            $display("  would have reported as covered while never sampling them.");

            $display("");
            $display("==============================================================");
            $display("  checks %0d   errors %0d", checks, errors);
            $display("  F7 COVERAGE MODEL: %0d bands x %0d outcomes. Pre-pass: %0d REACHED,",
                     N_BAND, N_OUT, closure_target);
            $display("  %0d EXCLUDED by argument (the only illegal bins), %0d OPEN.",
                     n_excluded, n_unreachable);
            $display("  Closure over the REACHED cells: %0s. Illegal-bin hits: %0d.",
                     (closure_frames >= 0) ? "met" : "NOT met", illegal_hits);
            if (close_random >= 0)
                $display("  Closure cost: %0d frames pure-random vs %0d coverage-driven.",
                         close_random, close_steered);
            else
                $display("  Closure cost: pure random did NOT close in budget; coverage-");
            if (close_random < 0)
                $display("  driven closed in %0d frames. A cell can be reachable and still",
                         close_steered);
            if (close_random < 0)
                $display("  be out of a uniform generator's reach -- which is what steering is for.");
            if (refutations > 0) begin
                $display("  %0d OPEN cells were REFUTED by the random run: the pre-pass had",
                         refutations);
                $display("  not reached them and they are reachable. Only ARGUED exclusions");
                $display("  are asserted here, which is why that was a result and not a");
                $display("  false failure.");
            end
            else begin
                $display("  No OPEN cell was refuted on this seed. The three-way");
                $display("  classification is still what makes that safe: on the first run");
                $display("  of this bench, with two verdicts, band 3 x LOST fired as an");
                $display("  illegal bin 21 frames in, against correct RTL.");
            end
            $display("  The closure criterion deliberately excludes any implication of");
            $display("  the form 'beyond the limit => error': C3 shows that is false and");
            $display("  data-dependent, so it is not a bin and not an assertion.");
            if (errors == 0) $display("RESULT: PASS"); else $display("RESULT: FAIL");
            $display("==============================================================");
        end
    endtask

    // =================================================================
    // Main
    // =================================================================
    integer budget = 400;

    initial begin
        // EXACTLY 09-25's trial set, so T0's cross-check against that
        // session's numbers is a comparison and not a coincidence.
        pat[0] = 8'h00; pat[1] = 8'hFF; pat[2] = 8'hAA;
        pat[3] = 8'h55; pat[4] = 8'h01; pat[5] = 8'h80;
        // the same SIZE of trial set with two bytes swapped -- T0b's experiment
        alt[0] = 8'h00; alt[1] = 8'hFF; alt[2] = 8'hAA;
        alt[3] = 8'h55; alt[4] = 8'h3C; alt[5] = 8'h81;
        if (!$value$plusargs("seed=%d", seed))   seed = 1;
        if (!$value$plusargs("budget=%d", budget)) budget = 400;
        phase_seed = seed * 977 + 13;
        cov_reset;

        $display("==============================================================");
        $display("UART BAUD-ERROR COVERAGE MODEL   seed=%0d", seed);
        $display("  DUT bit period : %0.1f ns  (16 x (BAUD_DIV=%0d + 1) x %0.1f ns)",
                 BIT_NS_NOM, BAUD_DIV_CFG, CLK_NS);
        $display("  one oversample tick : %0.1f ns = 1/16 bit", OS_TICK_NS);
        $display("  loopback       : OFF everywhere (a baud error is invisible in it)");
        $display("==============================================================");

        rst_n = 1'b0;
        repeat (6) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);

        t0_measure_limits;
        t0b_pattern_dependence;
        t0c_refine;
        t1_old_coverpoint_is_blind;
        t2_edge_disagreement;
        t3_phase_probes;
        t4_reachability_prepass;
        t4b_space_matters;
        t5_closure(budget, 1'b0, close_random);
        t5_closure(budget, 1'b1, close_steered);
        expect_true(close_steered >= 0,
                    "coverage-driven closure not met within budget");
        report;
        $finish;
    end

    initial begin
        #40_000_000;
        $display("TIMEOUT");
        $display("RESULT: FAIL");
        $finish;
    end

endmodule
