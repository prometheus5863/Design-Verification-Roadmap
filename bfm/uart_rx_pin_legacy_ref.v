// bfm/uart_rx_pin_legacy_ref.v
//
// THE REFERENCE, NOT A SECOND DRIVER.  Do not instantiate this in a
// testbench that tests the DUT.  Its only consumer is
// examples/phase6_bfm_equivalence/, where it exists so that the
// extraction of bfm/uart_rx_pin_bfm.v can be PROVED to be a pure
// refactor rather than asserted to be one.
//
// Inside `drive_frame_legacy` is the body of the `task drive_frame` that
// lived, duplicated verbatim, in examples/phase6_rx_pin_driver/
// uart_rx_pin_tb.v and examples/phase6_baud_error_coverage/
// uart_baud_cov_tb.v up to 2026-09-27.  It is copied CHARACTER FOR
// CHARACTER from the former, including its comments.  If a future session
// needs to know what the pre-BFM driver did, this is the answer, and
// `git log -p` is not needed to get it.
//
// WHY THE TIMEBASE IS RE-DERIVED IN HERE RATHER THAN PASSED IN
// -----------------------------------------------------------
// The interesting half of the equivalence question is not "do two
// identical delay statements agree" -- they trivially do.  It is whether
// the CONVERSION differs: the old path computes a `real` nanosecond bit
// period and lets `#(real)` quantise it to the 1ps precision of a
// `timescale 1ns/1ps` module, while the BFM path rounds that same real to
// an integer number of picoseconds in the caller and delays by the
// integer.  Those are two different roundings of the same product and
// they are not obviously the same number.
//
// So this module takes the baud error in BASIS POINTS -- the same unit the
// phase6 benches sweep in -- and recomputes `drv_bit_ns` internally with
// the same expression they used.  The equivalence bench gives the BFM the
// same eps_bp, converts it the BFM's way, and compares the resulting
// waveforms at ps resolution.  Anything the conversion does wrong shows
// up as a timestamp difference.
//
// `timescale is 1ns/1ps, matching the benches this code came from.  That
// is load-bearing: the same source under a 1ps/1ps timescale would make
// every delay a thousand times too short, which is precisely why the BFM
// could not simply be this file with a different header.

`timescale 1ns / 1ps

module uart_rx_pin_legacy_ref #(
    parameter real BIT_NS_NOM = 320.0
) (
    output reg         rx,
    input              go,
    output reg         busy,
    output reg [31:0]  done_cnt,

    input      [1:0]   mode,
    input      [7:0]   data,
    input      [1:0]   par,
    input              two_stop,
    input              bad_stop,
    input              bad_par,
    input  signed [31:0] eps_bp,          // baud error, 1 bp = 0.01%
    input      [31:0]  phase_ns,
    input      [31:0]  glitch_num,        // runt width = BIT_NS_NOM*num/den
    input      [31:0]  glitch_den
);

    localparam [1:0] MODE_FRAME  = 2'd0,
                     MODE_GLITCH = 2'd1,
                     MODE_IDLE   = 2'd2;

    localparam [1:0] PAR_NONE = 2'b00, PAR_EVEN = 2'b01, PAR_ODD = 2'b10;

    initial begin
        rx       = 1'b1;
        busy     = 1'b0;
        done_cnt = 32'd0;
    end

    // -----------------------------------------------------------------
    // VERBATIM from examples/phase6_rx_pin_driver/uart_rx_pin_tb.v as of
    // commit 2390970 (2026-09-26).  Comments included.  The only edits
    // are the task name (to avoid colliding with the wrapper below) and
    // the removal of the `rx` argument, which was a module-level reg
    // there and is a module-level reg here too.
    // -----------------------------------------------------------------
    // THE PIN DRIVER.  Its only timebase is drv_bit_ns.
    // -----------------------------------------------------------------
    // bad_stop: drive the (first) stop bit LOW instead of high.
    // bad_par : invert the parity bit that would otherwise be correct.
    task drive_frame_legacy(input [7:0] data, input [1:0] par, input two_stop,
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
    task drive_glitch_legacy(input real width_ns);
        begin
            rx = 1'b0;
            #(width_ns);
            rx = 1'b1;
        end
    endtask

    task idle_gap_legacy(input real n_bits, input real drv_bit_ns);
        begin
            rx = 1'b1;
            #(n_bits * drv_bit_ns);
        end
    endtask

    // -----------------------------------------------------------------
    // Handshake wrapper.  Same protocol as the BFM so that one bench can
    // run both from one stimulus stream.  `drv_bit_ns` is recomputed here
    // with the phase6 benches' own expression -- see the header.
    // -----------------------------------------------------------------
    real bns;

    always begin
        wait (go === 1'b1);
        busy = 1'b1;
        bns  = BIT_NS_NOM * (1.0 + eps_bp / 10000.0);
        case (mode)
            MODE_FRAME: begin
                // `drive_phased`'s prefix, verbatim: `#(phase_ns * 1.0);`
                if (phase_ns != 0) #(phase_ns * 1.0);
                drive_frame_legacy(data, par, two_stop, bns, bad_stop, bad_par);
            end
            MODE_GLITCH: begin
                if (phase_ns != 0) #(phase_ns * 1.0);
                drive_glitch_legacy(BIT_NS_NOM * glitch_num / glitch_den);
            end
            MODE_IDLE: idle_gap_legacy(1.0, bns);
            default: rx = 1'b1;
        endcase
        done_cnt = done_cnt + 32'd1;
        busy     = 1'b0;
        wait (go === 1'b0);
    end

endmodule
