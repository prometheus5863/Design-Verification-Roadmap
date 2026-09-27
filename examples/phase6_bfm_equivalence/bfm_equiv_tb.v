// examples/phase6_bfm_equivalence/bfm_equiv_tb.v
//
// Proves that extracting the duplicated `task drive_frame` into
// bfm/uart_rx_pin_bfm.v is a PURE REFACTOR, by running the BFM and a
// verbatim copy of the old task (bfm/uart_rx_pin_legacy_ref.v) side by
// side on the same stimulus and comparing every transition of `rx` at
// PICOSECOND resolution with ZERO tolerance.
//
// There is no DUT in this bench.  That is deliberate.  A refactor check
// that runs through the DUT answers "did the receiver still get the
// byte", which is a much weaker question than "is the waveform the same"
// -- a 1 ps error is invisible to the receiver and would pass such a
// check, then reappear later as an unreproducible tolerance limit.  The
// clock here exists only for T2, which asks where the transitions sit
// relative to the DUT's clock grid.
//
// WHY A ZERO-TOLERANCE CHECK IS THE POINT
// ---------------------------------------
// 2026-09-17 in the graphene repo, and 2026-09-25 and 09-26 here, all
// landed the same lesson from different directions: a plausible-range
// check passes what an exact check catches.  This bench has no range.
// Two transition lists either are the same list or they are not.
//
// `timescale is 1ps/1ps so that $time reports picoseconds.  The BFM is
// also 1ps/1ps; the legacy reference is 1ns/1ps, as the benches it came
// from were.  The three timescales coexisting is not an accident to be
// tidied up -- it is the thing under test.
//
// Run:  bash examples/phase6_bfm_equivalence/run_bfm_equiv.sh

`timescale 1ps / 1ps

module bfm_equiv_tb;

    // Nominal: 10 ns clock, BAUD_DIV = 1, so one bit is 16*(1+1) = 32
    // clock cycles = 320 ns = 320000 ps.  Same numbers as
    // examples/phase6_baud_error_coverage/.
    localparam real    CLK_NS      = 10.0;
    localparam integer BAUD_DIV    = 1;
    localparam real    BIT_NS_NOM  = CLK_NS * 16.0 * (BAUD_DIV + 1);
    localparam integer CLK_PS      = 10000;
    localparam integer BIT_PS_NOM  = 320000;
    localparam integer CYC_PER_BIT = 32;

    localparam [1:0] MODE_FRAME = 2'd0, MODE_GLITCH = 2'd1, MODE_IDLE = 2'd2;
    localparam [1:0] PAR_NONE = 2'b00, PAR_EVEN = 2'b01, PAR_ODD = 2'b10;

    // A clock, for T2 only.  Nothing in the drivers reads it.
    reg clk = 1'b0;
    always #(CLK_PS / 2) clk = ~clk;
    integer clk_count = 0;
    always @(posedge clk) clk_count = clk_count + 1;

    // -----------------------------------------------------------------
    // Shared stimulus registers -- ONE set, feeding BOTH drivers.  If the
    // two drivers were given separately-computed stimulus, a difference in
    // the stimulus could masquerade as agreement or as disagreement, which
    // is 09-26 item 2's mistake in a different costume.
    // -----------------------------------------------------------------
    reg         go       = 1'b0;
    reg  [1:0]  mode     = MODE_FRAME;
    reg  [7:0]  data     = 8'h00;
    reg  [1:0]  par      = PAR_NONE;
    reg         two_stop = 1'b0;
    reg         bad_stop = 1'b0;
    reg         bad_par  = 1'b0;
    reg signed [31:0] eps_bp   = 0;
    reg  [31:0] phase_ns = 0;
    reg  [31:0] glitch_num = 3, glitch_den = 16;

    // The BFM's timebase, derived from eps_bp the BFM's way.
    reg  [31:0] bit_ps    = BIT_PS_NOM;
    reg  [31:0] phase_ps  = 0;
    reg  [31:0] glitch_ps = 60000;

    function [31:0] ps_round(input real ns);
        begin
            ps_round = $rtoi(ns * 1000.0 + 0.5);
        end
    endfunction

    wire rx_bfm, rx_ref;
    wire busy_bfm, busy_ref;
    wire [31:0] dc_bfm, dc_ref;

    uart_rx_pin_bfm u_bfm (
        .rx(rx_bfm), .go(go), .busy(busy_bfm), .done_cnt(dc_bfm),
        .mode(mode), .data(data), .par(par), .two_stop(two_stop),
        .bad_stop(bad_stop), .bad_par(bad_par),
        .bit_ps(bit_ps), .phase_ps(phase_ps), .glitch_ps(glitch_ps)
    );

    uart_rx_pin_legacy_ref #(.BIT_NS_NOM(BIT_NS_NOM)) u_ref (
        .rx(rx_ref), .go(go), .busy(busy_ref), .done_cnt(dc_ref),
        .mode(mode), .data(data), .par(par), .two_stop(two_stop),
        .bad_stop(bad_stop), .bad_par(bad_par),
        .eps_bp(eps_bp), .phase_ns(phase_ns),
        .glitch_num(glitch_num), .glitch_den(glitch_den)
    );

    // -----------------------------------------------------------------
    // Transition recorders
    // -----------------------------------------------------------------
    localparam integer MAXT = 64;
    integer n_bfm = 0, n_ref = 0;
    integer t_bfm [0:MAXT-1];
    integer t_ref [0:MAXT-1];
    reg     v_bfm [0:MAXT-1];
    reg     v_ref [0:MAXT-1];
    integer t0 = 0;
    reg     recording = 1'b0;

    always @(rx_bfm) if (recording && n_bfm < MAXT) begin
        t_bfm[n_bfm] = $time - t0; v_bfm[n_bfm] = rx_bfm; n_bfm = n_bfm + 1;
    end
    always @(rx_ref) if (recording && n_ref < MAXT) begin
        t_ref[n_ref] = $time - t0; v_ref[n_ref] = rx_ref; n_ref = n_ref + 1;
    end

    integer end_bfm = 0, end_ref = 0;

    integer checks = 0, errors = 0;
    integer trials = 0;

    task fail(input [8*100:1] what);
        begin
            errors = errors + 1;
            $display("  ** FAIL: %0s", what);
        end
    endtask

    // -----------------------------------------------------------------
    // One trial: set the stimulus, start BOTH drivers in the same delta,
    // wait for both, compare.
    // -----------------------------------------------------------------
    // `first_mismatch` is reported rather than just a count, because a
    // count tells you a refactor is wrong and an index tells you which
    // bit boundary it is wrong at.
    integer first_mismatch;
    task run_trial(input [8*40:1] tag);
        integer k;
        begin
            trials = trials + 1;
            // Derive the BFM's integer timebase from the SAME eps_bp the
            // reference will use, the BFM's way.
            bit_ps    = ps_round(BIT_NS_NOM * (1.0 + eps_bp / 10000.0));
            phase_ps  = phase_ns * 1000;
            glitch_ps = ps_round(BIT_NS_NOM * glitch_num / glitch_den);

            n_bfm = 0; n_ref = 0;
            t0 = $time;
            recording = 1'b1;
            go = 1'b1;
            wait (busy_bfm === 1'b1 && busy_ref === 1'b1);
            go = 1'b0;
            fork
                begin wait (busy_bfm === 1'b0); end_bfm = $time - t0; end
                begin wait (busy_ref === 1'b0); end_ref = $time - t0; end
            join
            recording = 1'b0;

            // --- the comparison, with no tolerance ---
            checks = checks + 1;
            if (n_bfm !== n_ref) begin
                $display("  ** FAIL[%0s]: transition COUNT %0d (bfm) vs %0d (ref)",
                         tag, n_bfm, n_ref);
                errors = errors + 1;
            end else begin
                first_mismatch = -1;
                for (k = 0; k < n_bfm; k = k + 1)
                    if (first_mismatch < 0 &&
                        (t_bfm[k] !== t_ref[k] || v_bfm[k] !== v_ref[k]))
                        first_mismatch = k;
                if (first_mismatch >= 0) begin
                    $display("  ** FAIL[%0s]: transition %0d bfm t=%0d v=%b  ref t=%0d v=%b  (delta %0d ps)",
                             tag, first_mismatch,
                             t_bfm[first_mismatch], v_bfm[first_mismatch],
                             t_ref[first_mismatch], v_ref[first_mismatch],
                             t_bfm[first_mismatch] - t_ref[first_mismatch]);
                    errors = errors + 1;
                end
            end
            checks = checks + 1;
            if (end_bfm !== end_ref) begin
                $display("  ** FAIL[%0s]: completion time %0d (bfm) vs %0d (ref) ps",
                         tag, end_bfm, end_ref);
                errors = errors + 1;
            end
            #(BIT_PS_NOM * 2);
        end
    endtask

    // -----------------------------------------------------------------
    // Trial-set tables
    // -----------------------------------------------------------------
    // eps values chosen to be AWKWARD, not round: if the two roundings
    // differ at all they differ on products that do not land on a ps
    // boundary, and a table of multiples of 100 bp would miss exactly
    // those.  1234 bp and 4751 bp are there for that reason; 4751 bp is
    // also the eps at which 09-27's graphene session found a blind spot,
    // reused here only because it is an unlovely number.
    localparam integer N_EPS = 16;
    integer eps_tab [0:N_EPS-1];
    localparam integer N_DATA = 8;
    integer data_tab [0:N_DATA-1];

    integer i, j, e, cfg, seed;
    integer n_bits_expected;

    // -----------------------------------------------------------------
    // T2: exact clock-grid alignment (validation V2)
    // -----------------------------------------------------------------
    // At eps = 0 and phase = 0 the BFM must be indistinguishable from the
    // cycle-counted Phase 4 UVM driver it replaces, and "indistinguishable"
    // has an exact value here: transition m must occur at exactly
    // boundary(m) * CYC_PER_BIT * CLK_PS picoseconds, on a clock edge.
    //
    // THE EXPECTED TRANSITION LIST IS DERIVED FROM THE FRAME DEFINITION,
    // not written down.  The first version of this check hardcoded "0xAA
    // 8N1 gives 10 transitions, every span 32 cycles" and was WRONG: the
    // start bit is 0 and 0xAA's LSB is 0, so the first boundary has no
    // transition and the first span is 64 cycles, not 32.  The bench
    // reported 8 transitions and one bad span and the BFM was right.  A
    // hand-written expected value is a second implementation with no
    // tests, which is 09-26 item 2's lesson at the scale of one constant --
    // so the constant was replaced by the derivation rather than corrected
    // to 8.
    task t2_grid_alignment;
        integer k, j, nb, exp_n, bad_t, bad_grid, bad_n, cfgs;
        reg     lvl [0:15];
        integer exp_t [0:15];
        reg     pbit;
        begin
            $display("T2  exact clock-grid alignment at eps=0, phase=0 (V2)");
            $display("    expected transitions DERIVED from the frame, not hardcoded");
            bad_t = 0; bad_grid = 0; bad_n = 0; cfgs = 0;
            for (k = 0; k < 40; k = k + 1) begin
                data     = data_tab[k % N_DATA][7:0];
                par      = ((k / N_DATA) % 3 == 0) ? PAR_NONE :
                           (((k / N_DATA) % 3 == 1) ? PAR_EVEN : PAR_ODD);
                two_stop = ((k / (N_DATA*3)) % 2) != 0;
                bad_stop = (k >= 32);
                bad_par  = 1'b0;
                eps_bp   = 0; phase_ns = 0; mode = MODE_FRAME;

                // Build the frame's level sequence.  lvl[0] is the idle level
                // BEFORE the start bit, so boundary j (between lvl[j] and
                // lvl[j+1]) falls at j*CYC_PER_BIT*CLK_PS after the start edge.
                nb = 0;
                lvl[nb] = 1'b1; nb = nb + 1;                    // idle
                lvl[nb] = 1'b0; nb = nb + 1;                    // start
                for (j = 0; j < 8; j = j + 1) begin
                    lvl[nb] = data[j]; nb = nb + 1;             // LSB first
                end
                if (par != PAR_NONE) begin
                    pbit = (par == PAR_EVEN) ? ^data : ~(^data);
                    lvl[nb] = bad_par ? ~pbit : pbit; nb = nb + 1;
                end
                lvl[nb] = bad_stop ? 1'b0 : 1'b1; nb = nb + 1;  // stop 1
                if (two_stop) begin
                    lvl[nb] = 1'b1; nb = nb + 1;                // stop 2
                end
                lvl[nb] = 1'b1; nb = nb + 1;                    // return to idle

                exp_n = 0;
                for (j = 0; j < nb - 1; j = j + 1)
                    if (lvl[j] !== lvl[j+1]) begin
                        exp_t[exp_n] = j * CYC_PER_BIT * CLK_PS;
                        exp_n = exp_n + 1;
                    end

                run_trial("T2 grid");
                cfgs = cfgs + 1;
                checks = checks + 1;
                if (n_bfm !== exp_n) begin
                    $display("  ** FAIL: data=%02h par=%0d 2stop=%0b badstop=%0b: %0d transitions, derived %0d",
                             data, par, two_stop, bad_stop, n_bfm, exp_n);
                    errors = errors + 1; bad_n = bad_n + 1;
                end else begin
                    for (j = 0; j < n_bfm; j = j + 1) begin
                        if (t_bfm[j] !== exp_t[j]) begin
                            if (bad_t == 0)
                                $display("  ** FAIL: data=%02h transition %0d at %0d ps, derived %0d ps",
                                         data, j, t_bfm[j], exp_t[j]);
                            bad_t = bad_t + 1;
                        end
                        if ((t_bfm[j] % CLK_PS) !== 0) bad_grid = bad_grid + 1;
                    end
                end
            end
            checks = checks + 2;
            $display("    %0d frame configs, off-grid transitions: %0d, wrong timestamps: %0d, wrong counts: %0d",
                     cfgs, bad_grid, bad_t, bad_n);
            if (bad_grid != 0) fail("T2: a transition does not land on the DUT clock grid");
            if (bad_t != 0) fail("T2: a transition is not at boundary*CYC_PER_BIT*CLK_PS");
            if (bad_grid == 0 && bad_t == 0 && bad_n == 0)
                $display("    every bit boundary is EXACTLY %0d clock cycles -- the BFM at eps=0",
                         CYC_PER_BIT);
            $display("    reproduces the cycle-counted driver's grid exactly");
            $display("");
        end
    endtask

    // -----------------------------------------------------------------
    // T3: the NEGATIVE control (validation V4)
    // -----------------------------------------------------------------
    // If the BFM agreed with a cycle-counted driver at every eps, its
    // "independent" timebase would be decorative.  data=0x00 in 8N1 gives
    // exactly two transitions -- the start-bit fall and the stop-bit rise
    // nine bit periods later -- so the interval is exactly 9*bit_ps and can
    // be predicted in closed form for every eps.
    task t3_negative_control;
        integer k, span, want, bad;
        begin
            $display("T3  NEGATIVE control: the timebase must actually move (V4)");
            bad = 0;
            for (k = 0; k < N_EPS; k = k + 1) begin
                eps_bp = eps_tab[k]; phase_ns = 0; data = 8'h00;
                par = PAR_NONE; two_stop = 1'b0; bad_stop = 1'b0;
                bad_par = 1'b0; mode = MODE_FRAME;
                run_trial("T3 eps");
                if (n_bfm != 2) begin
                    fail("T3: 0x00 8N1 should give exactly 2 transitions");
                    bad = bad + 1;
                end else begin
                    span = t_bfm[1] - t_bfm[0];
                    want = 9 * bit_ps;
                    checks = checks + 1;
                    if (span !== want) begin
                        $display("  ** FAIL: eps=%0d bp  span %0d ps, want 9*bit_ps = %0d",
                                 eps_bp, span, want);
                        errors = errors + 1; bad = bad + 1;
                    end
                    if (eps_bp != 0 && span === 9 * BIT_PS_NOM) begin
                        fail("T3: eps != 0 did not move the frame at all");
                        bad = bad + 1;
                    end
                end
            end
            $display("    %0d eps values, exact 9*bit_ps span, %0d bad", N_EPS, bad);
            $display("");
        end
    endtask

    // -----------------------------------------------------------------
    initial begin
        eps_tab[0]=0;      eps_tab[1]=1;      eps_tab[2]=-1;    eps_tab[3]=5;
        eps_tab[4]=-5;     eps_tab[5]=37;     eps_tab[6]=-37;   eps_tab[7]=250;
        eps_tab[8]=-250;   eps_tab[9]=625;    eps_tab[10]=-625; eps_tab[11]=1234;
        eps_tab[12]=-1234; eps_tab[13]=4751;  eps_tab[14]=-4751;eps_tab[15]=7;
        data_tab[0]=8'h00; data_tab[1]=8'hFF; data_tab[2]=8'hAA; data_tab[3]=8'h55;
        data_tab[4]=8'h01; data_tab[5]=8'h80; data_tab[6]=8'h3C; data_tab[7]=8'h81;

        $display("=========================================================");
        $display(" BFM / legacy-task equivalence -- zero tolerance, ps resolution");
        $display(" bfm/uart_rx_pin_bfm.v  vs  bfm/uart_rx_pin_legacy_ref.v");
        $display(" nominal bit = %0d ps = %0d clk cycles", BIT_PS_NOM, CYC_PER_BIT);
        $display("=========================================================");
        $display("");

        #(BIT_PS_NOM);

        // --- T1: the structured sweep (validation V1, question Q1) ---
        $display("T1  structured sweep: 24 frame configs x %0d data x %0d eps (V1)",
                 N_DATA, N_EPS);
        for (cfg = 0; cfg < 24; cfg = cfg + 1) begin
            par      = (cfg % 3 == 0) ? PAR_NONE : ((cfg % 3 == 1) ? PAR_EVEN : PAR_ODD);
            two_stop = ((cfg / 3) % 2) != 0;
            bad_stop = ((cfg / 6) % 2) != 0;
            bad_par  = ((cfg / 12) % 2) != 0;
            mode     = MODE_FRAME;
            phase_ns = 0;
            for (i = 0; i < N_DATA; i = i + 1) begin
                data = data_tab[i][7:0];
                for (j = 0; j < N_EPS; j = j + 1) begin
                    eps_bp = eps_tab[j];
                    run_trial("T1");
                end
            end
        end
        $display("    %0d trials, %0d checks so far, %0d errors", trials, checks, errors);
        $display("");

        // --- T1b: random trials including a random initial edge phase ---
        // The structured sweep holds phase at 0.  Phase is the variable
        // 09-25 measured moving a tolerance limit by 0.69% of eps, so a
        // refactor check that never varies it is checking the easy half.
        $display("T1b random trials with a random initial edge phase (V1)");
        seed = 32'h5EED_1234;
        for (i = 0; i < 400; i = i + 1) begin
            data     = $random(seed);
            e        = $random(seed) % 7000;
            eps_bp   = e;
            par      = {$random(seed)} % 3;
            two_stop = {$random(seed)} % 2;
            bad_stop = {$random(seed)} % 2;
            bad_par  = {$random(seed)} % 2;
            phase_ns = {$random(seed)} % 20;
            mode     = MODE_FRAME;
            run_trial("T1b");
        end
        $display("    %0d trials cumulative, %0d errors", trials, errors);
        $display("");

        // --- T1c: the glitch and idle modes ---
        $display("T1c glitch and idle modes (V1)");
        mode = MODE_GLITCH; eps_bp = 0; phase_ns = 0;
        glitch_num = 3; glitch_den = 16;  run_trial("T1c glitch 3/16");
        glitch_num = 7; glitch_den = 16;  run_trial("T1c glitch 7/16");
        glitch_num = 1; glitch_den = 3;   run_trial("T1c glitch 1/3");
        mode = MODE_IDLE;
        eps_bp = 0;    run_trial("T1c idle eps=0");
        eps_bp = 1234; run_trial("T1c idle eps=1234");
        eps_bp = -37;  run_trial("T1c idle eps=-37");
        mode = MODE_FRAME;
        $display("    %0d trials cumulative, %0d errors", trials, errors);
        $display("");

        t2_grid_alignment;
        t3_negative_control;

        $display("=========================================================");
        $display(" trials : %0d", trials);
        $display(" checks : %0d", checks);
        $display(" errors : %0d", errors);
        if (errors == 0)
            $display(" RESULT : PASS -- the extraction is a pure refactor at ps resolution");
        else
            $display(" RESULT : FAIL");
        $display("=========================================================");
        $finish;
    end

endmodule
