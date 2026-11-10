// examples/phase6_cdc_basics/cdc_crossings_tb.v
//
// Self-checking testbench for the Phase 6 CDC basics example.
//
// THE POINT OF THIS BENCH, stated before the code, because it is not the
// usual point of a CDC demo:
//
//   A zero-delay RTL simulation CANNOT show the multi-bit CDC bug.  With
//   every bit of a vector changing at the same simulation instant, a
//   per-bit two-flop synchroniser samples a perfectly coherent snapshot,
//   every time, forever.  The bench measures that (check C2) and reports
//   it as a WARNING-shaped exact zero rather than a pass.
//
//   To see the bug you must MODEL the physical fact the zero-delay
//   simulation discards: the bits do not arrive at the destination flops
//   at the same moment.  SKEW_UNIT below does exactly that and nothing
//   else.  With it on, the naive binary crossing breaks (C3) and the
//   Gray-coded crossing does not (C4) -- same model, same stimulus, one
//   difference.  That pair is the real content.
//
//   The conclusion a reader should take: CDC is a STRUCTURAL property and
//   belongs to a static CDC checker, not to simulation.  A green
//   simulation of a multi-bit crossing is evidence of almost nothing,
//   which is why C2 exists and is phrased the way it is.
//
// Run with:  make -f Makefile  (or run_cdc_sim.sh), which runs BOTH skew
// settings -- a single run can only ever show half of C2/C3.

`default_nettype none
`timescale 1ns/1ps

// Default to the plain zero-delay simulation; override on the command line
// with  iverilog -DSKEW_UNIT_NS=<ns>.
`ifndef SKEW_UNIT_NS
  `define SKEW_UNIT_NS 0
`endif

module cdc_crossings_tb;

    // ---------------------------------------------------------------
    // Parameters
    // ---------------------------------------------------------------
    parameter W            = 8;
    parameter CLK_A_HALF   = 5;    // clk_a period 10 ns  (fast, source)
    parameter CLK_B_HALF   = 17;   // clk_b period 34 ns  (slow, dest)
                                   // deliberately NON-HARMONIC with clk_a,
                                   // so the sampling phase drifts
    parameter PULSE_EVERY  = 16;   // clk_a cycles between source pulses
    parameter N_CLK_B      = 400;  // destination cycles to run
    parameter MAX_DELTA    = 8;    // largest coherent jump in the counter
                                   // between two clk_b samples.  clk_b is
                                   // 3.4x slower than clk_a, so a coherent
                                   // delta is 3 or 4; 8 is slack, and any
                                   // incoherent sample is off by tens.

    // SKEW_UNIT: per-bit arrival skew, in ns, at the destination flops.
    // 0 = the ordinary zero-delay simulation.  1 = each bit i arrives i ns
    // later than bit 0, which is less than one clk_a period (10 ns), so
    // the vector is still fully settled before the next source edge --
    // i.e. this is a MILD and physically ordinary amount of skew, not a
    // contrived one.
    //
    // Set from the command line with  iverilog -DSKEW_UNIT_NS=1.
    //
    // A MACRO AND NOT A PARAMETER, deliberately.  The first version used a
    // parameter and `iverilog -PSKEW_UNIT=1`, which SILENTLY DID NOTHING:
    // Icarus's -P needs a hierarchical path (-Ptb.SKEW_UNIT=1), so the
    // 'skewed' run was in fact a second zero-skew run, reported ALL_PASS,
    // and was indistinguishable from a successful skew run except that the
    // B2/B3 checks were quietly absent from the output.  A silent no-op on
    // the one knob this whole example turns is the worst available failure
    // mode, so the knob is a macro: a typo in it is a compile error rather
    // than a quiet pass.  Check K1 gates that the mode actually elaborated
    // is the mode the output claims.
    parameter SKEW_UNIT    = `SKEW_UNIT_NS;

    // ---------------------------------------------------------------
    // Clocks and reset
    // ---------------------------------------------------------------
    reg clk_a = 1'b0;
    reg clk_b = 1'b0;
    reg rst_n = 1'b0;

    always #CLK_A_HALF clk_a = ~clk_a;
    always #CLK_B_HALF clk_b = ~clk_b;

    // ---------------------------------------------------------------
    // SOURCE DOMAIN (clk_a): a free-running counter and a periodic pulse
    // ---------------------------------------------------------------
    reg  [W-1:0] bin_a = {W{1'b0}};
    reg  [31:0]  pulse_phase = 0;
    reg          pulse_a = 1'b0;
    integer      gen_count = 0;
    // gen_en quiesces the SOURCE before the destination counters are
    // compared.  Without it the bench compares a source-domain count
    // against a destination-domain count while a pulse is still in
    // flight, and P2's exact equality fails by one for a reason that has
    // nothing to do with the crossing being tested.  See the session note.
    reg          gen_en = 1'b1;

    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) begin
            bin_a       <= {W{1'b0}};
            pulse_phase <= 0;
            pulse_a     <= 1'b0;
        end else begin
            bin_a <= bin_a + 1'b1;
            if (!gen_en) begin
                pulse_phase <= 0;
                pulse_a     <= 1'b0;
            end else if (pulse_phase == PULSE_EVERY - 1) begin
                pulse_phase <= 0;
                pulse_a     <= 1'b1;
            end else begin
                pulse_phase <= pulse_phase + 1;
                pulse_a     <= 1'b0;
            end
        end
    end

    // count what the source actually emitted
    always @(posedge clk_a) if (rst_n && pulse_a) gen_count = gen_count + 1;

    wire [W-1:0] gray_a;
    bin2gray #(.W(W)) u_b2g (.bin(bin_a), .gray(gray_a));

    // ---------------------------------------------------------------
    // THE SKEW MODEL.  This is the only non-synthesisable idea in the
    // example and it lives here, in the testbench, on purpose.
    // ---------------------------------------------------------------
    wire [W-1:0] bin_skewed;
    wire [W-1:0] gray_skewed;

    generate
        if (SKEW_UNIT == 0) begin : g_no_skew
            assign bin_skewed  = bin_a;
            assign gray_skewed = gray_a;
        end else begin : g_skew
            // bit i arrives SKEW_UNIT*i later than bit 0
            assign #(0*SKEW_UNIT) bin_skewed[0] = bin_a[0];
            assign #(1*SKEW_UNIT) bin_skewed[1] = bin_a[1];
            assign #(2*SKEW_UNIT) bin_skewed[2] = bin_a[2];
            assign #(3*SKEW_UNIT) bin_skewed[3] = bin_a[3];
            assign #(4*SKEW_UNIT) bin_skewed[4] = bin_a[4];
            assign #(5*SKEW_UNIT) bin_skewed[5] = bin_a[5];
            assign #(6*SKEW_UNIT) bin_skewed[6] = bin_a[6];
            assign #(7*SKEW_UNIT) bin_skewed[7] = bin_a[7];
            assign #(0*SKEW_UNIT) gray_skewed[0] = gray_a[0];
            assign #(1*SKEW_UNIT) gray_skewed[1] = gray_a[1];
            assign #(2*SKEW_UNIT) gray_skewed[2] = gray_a[2];
            assign #(3*SKEW_UNIT) gray_skewed[3] = gray_a[3];
            assign #(4*SKEW_UNIT) gray_skewed[4] = gray_a[4];
            assign #(5*SKEW_UNIT) gray_skewed[5] = gray_a[5];
            assign #(6*SKEW_UNIT) gray_skewed[6] = gray_a[6];
            assign #(7*SKEW_UNIT) gray_skewed[7] = gray_a[7];
        end
    endgenerate

    // Witness for K1: how often the skewed copy differs from the source.
    // With no skew path elaborated, bin_skewed is a plain alias of bin_a
    // and can NEVER differ; with skew it must differ somewhere.
    integer skew_witness = 0;
    always @(bin_skewed or bin_a)
        if (rst_n && (bin_skewed !== bin_a)) skew_witness = skew_witness + 1;

    // ---------------------------------------------------------------
    // CROSSING 1 (WRONG): an 8-bit vector through per-bit 2FF syncs
    // CROSSING 2 (RIGHT): the same counter Gray-coded first
    // ---------------------------------------------------------------
    wire [W-1:0] sync_bin;
    wire [W-1:0] sync_gray;
    wire [W-1:0] dec_gray;

    cdc_sync_2ff #(.W(W)) u_sync_bin (
        .clk_dst(clk_b), .rst_n(rst_n),
        .d_src(bin_skewed), .q_dst(sync_bin));

    cdc_sync_2ff #(.W(W)) u_sync_gray (
        .clk_dst(clk_b), .rst_n(rst_n),
        .d_src(gray_skewed), .q_dst(sync_gray));

    gray2bin #(.W(W)) u_g2b (.gray(sync_gray), .bin(dec_gray));

    // ---------------------------------------------------------------
    // CROSSING 3 (WRONG): a one-cycle pulse sampled by a slower clock
    // CROSSING 4 (RIGHT): the same pulse carried as a level toggle
    // ---------------------------------------------------------------
    wire sync_pulse_naive;
    reg  sync_pulse_naive_d = 1'b0;
    integer obs_naive = 0;

    cdc_sync_2ff #(.W(1)) u_sync_pulse (
        .clk_dst(clk_b), .rst_n(rst_n),
        .d_src(pulse_a), .q_dst(sync_pulse_naive));

    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) sync_pulse_naive_d <= 1'b0;
        else        sync_pulse_naive_d <= sync_pulse_naive;
    end
    always @(posedge clk_b)
        if (rst_n && sync_pulse_naive && !sync_pulse_naive_d)
            obs_naive = obs_naive + 1;

    wire toggle_a, pulse_b_hs;
    integer obs_hs = 0;

    cdc_pulse_toggle_src u_tog_src (
        .clk_src(clk_a), .rst_n(rst_n),
        .pulse_src(pulse_a), .toggle_src(toggle_a));

    cdc_pulse_toggle_dst u_tog_dst (
        .clk_dst(clk_b), .rst_n(rst_n),
        .toggle_src(toggle_a), .pulse_dst(pulse_b_hs));

    always @(posedge clk_b) if (rst_n && pulse_b_hs) obs_hs = obs_hs + 1;

    // ---------------------------------------------------------------
    // COHERENCY MEASUREMENT in the destination domain
    // ---------------------------------------------------------------
    integer samples      = 0;
    integer incoh_bin    = 0;
    integer incoh_gray   = 0;
    reg [W-1:0] prev_bin  = {W{1'b0}};
    reg [W-1:0] prev_gray = {W{1'b0}};
    reg         primed    = 1'b0;
    integer delta_bin, delta_gray;
    integer first_bad_bin_time, first_bad_bin_prev, first_bad_bin_got;

    initial begin
        first_bad_bin_time = -1;
        first_bad_bin_prev = -1;
        first_bad_bin_got  = -1;
    end

    always @(posedge clk_b) begin
        if (rst_n) begin
            if (primed) begin
                samples   = samples + 1;
                delta_bin  = (sync_bin - prev_bin)  & ((1<<W)-1);
                delta_gray = (dec_gray - prev_gray) & ((1<<W)-1);
                if (delta_bin > MAX_DELTA) begin
                    incoh_bin = incoh_bin + 1;
                    if (first_bad_bin_time < 0) begin
                        first_bad_bin_time = $time;
                        first_bad_bin_prev = prev_bin;
                        first_bad_bin_got  = sync_bin;
                    end
                end
                if (delta_gray > MAX_DELTA) incoh_gray = incoh_gray + 1;
            end
            prev_bin  = sync_bin;
            prev_gray = dec_gray;
            primed    = 1'b1;
        end
    end

    // ---------------------------------------------------------------
    // 2FF LATENCY: an exactly-known value, so it is checked exactly
    // ---------------------------------------------------------------
    reg      lat_in = 1'b0;
    wire     lat_out;
    integer  edge_cnt = 0;
    integer  edge_at_in = -1;
    integer  lat_latency = -1;

    cdc_sync_2ff #(.W(1)) u_lat (
        .clk_dst(clk_b), .rst_n(rst_n), .d_src(lat_in), .q_dst(lat_out));

    always @(posedge clk_b) if (rst_n) edge_cnt = edge_cnt + 1;
    initial begin
        @(posedge lat_in);
        edge_at_in = edge_cnt;
        @(posedge lat_out);
        lat_latency = edge_cnt - edge_at_in;
    end

    // ---------------------------------------------------------------
    // Stimulus and reporting
    // ---------------------------------------------------------------
    integer n_pass = 0, n_fail = 0;

    task check;
        input [4095:0] name;
        input          ok;
        input [4095:0] detail;
        begin
            if (ok) begin
                n_pass = n_pass + 1;
                $display("  [PASS] %0s", name);
            end else begin
                n_fail = n_fail + 1;
                $display("  [FAIL] %0s", name);
            end
            $display("         %0s", detail);
        end
    endtask

    // 4096 bits = 512 characters.  The first draft used [1023:0] = 128
    // characters and the longer detail strings were SILENTLY TRUNCATED
    // FROM THE LEFT -- 'incoherent binary samples' printed as
    // 'coherent binary samples', i.e. the truncation inverted the
    // meaning of a reported result.  See the session note.
    reg [4095:0] d;
    reg [4095:0] BAR;

    initial begin
        BAR = "==========================================================";
        $display("%0s", BAR);
        $display("PHASE 6 -- CDC BASICS.  SKEW_UNIT = %0d ns (0 = plain zero-delay sim)", SKEW_UNIT);
        $display("clk_a period %0d ns (source), clk_b period %0d ns (dest)", 2*CLK_A_HALF, 2*CLK_B_HALF);
        $display("%0s", BAR);

        repeat (4) @(posedge clk_b);
        rst_n = 1'b1;

        // drive the latency probe between clk_b edges, well away from one
        repeat (2) @(posedge clk_b);
        #(CLK_B_HALF);
        lat_in = 1'b1;

        repeat (N_CLK_B) @(posedge clk_b);

        // QUIESCE the source, THEN drain.  The handshake needs 2 clk_b
        // edges for the synchroniser plus 1 for the edge detector; 16 is
        // ample and, more importantly, the source has stopped, so the
        // comparison below is exact BY CONSTRUCTION rather than by luck
        // with where the simulation happened to end.
        gen_en = 1'b0;
        repeat (16) @(posedge clk_b);

        $display("");
        $display("MEASURED");
        $display("  destination samples            : %0d", samples);
        $display("  incoherent binary samples      : %0d", incoh_bin);
        $display("  incoherent Gray samples        : %0d", incoh_gray);
        $display("  source pulses generated        : %0d", gen_count);
        $display("  pulses seen, naive crossing    : %0d", obs_naive);
        $display("  pulses seen, toggle handshake  : %0d", obs_hs);
        $display("  2FF latency, clk_b edges       : %0d", lat_latency);
        if (first_bad_bin_time >= 0)
            $display("  first binary incoherency       : t=%0d ns, prev=%0d, sampled=%0d",
                     first_bad_bin_time, first_bad_bin_prev, first_bad_bin_got);

        $display("");
        $display("CHECKS");

        $sformat(d, "latency = %0d clk_b edges; exactly 2 is the only correct answer for a 2-flop synchroniser", lat_latency);
        check("L1 the 2FF synchroniser costs EXACTLY 2 destination edges", lat_latency == 2, d);

        $sformat(d, "samples = %0d; a run that measured nothing would pass every check below vacuously", samples);
        check("S1 the run actually sampled the crossing", samples > 300, d);

        // K1 exists because of the -P no-op described at SKEW_UNIT above:
        // the run must PROVE which mode it is in rather than print a
        // heading that says so.
        $sformat(d, "SKEW_UNIT = %0d, and bin_skewed disagreed with bin_a %0d times during the run (must be 0 iff no skew path was elaborated)", SKEW_UNIT, skew_witness);
        check("K1 the skew mode actually elaborated matches the mode reported",
              (SKEW_UNIT == 0) == (skew_witness == 0), d);

        $sformat(d, "incoherent Gray samples = %0d of %0d", incoh_gray, samples);
        check("G1 the Gray-coded crossing is coherent on EVERY sample", incoh_gray == 0, d);

        if (SKEW_UNIT == 0) begin
            $sformat(d, "incoherent binary samples = %0d of %0d -- and this EXACT ZERO IS THE WARNING, not the result: a zero-delay sim cannot expose the bug", incoh_bin, samples);
            check("B1 zero-delay sim shows the BROKEN crossing as clean (the bug is invisible to simulation)", incoh_bin == 0, d);
        end else begin
            $sformat(d, "incoherent binary samples = %0d of %0d with only %0d ns/bit of skew", incoh_bin, samples, SKEW_UNIT);
            check("B2 with per-bit skew modelled, the binary crossing BREAKS", incoh_bin > 0, d);
            $sformat(d, "binary %0d incoherent vs Gray %0d -- same skew, same stimulus, same synchroniser; the only difference is the encoding", incoh_bin, incoh_gray);
            check("B3 and the Gray crossing survives the SAME skew (two-sided, so G1 is not vacuous)", incoh_bin > 0 && incoh_gray == 0, d);
        end

        $sformat(d, "generated = %0d, seen = %0d (%0d lost)", gen_count, obs_naive, gen_count - obs_naive);
        check("P1 the naive pulse crossing LOSES pulses to the slower clock", obs_naive < gen_count, d);

        $sformat(d, "generated = %0d, seen = %0d", gen_count, obs_hs);
        check("P2 the toggle handshake loses NONE (exact equality)", obs_hs == gen_count, d);

        $sformat(d, "naive %0d < handshake %0d = generated %0d", obs_naive, obs_hs, gen_count);
        check("P3 and the handshake strictly beats the naive path (two-sided, so P2 is not an accident of timing)",
              obs_hs > obs_naive && obs_hs == gen_count, d);

        $display("");
        $display("  %0d passed, %0d failed", n_pass, n_fail);
        $display("");
        if (n_fail == 0) $display("CDC_TB_RESULT: ALL_PASS");
        else             $display("CDC_TB_RESULT: FAILURES=%0d", n_fail);
        $finish;
    end

endmodule

`default_nettype wire
