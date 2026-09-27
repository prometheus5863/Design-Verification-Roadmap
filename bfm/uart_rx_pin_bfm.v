// bfm/uart_rx_pin_bfm.v
//
// THE single UART RX pin driver for this repository.
//
// WHY THIS FILE EXISTS
// --------------------
// Until 2026-09-27 the pin driver was a `task drive_frame` duplicated
// VERBATIM in two testbenches -- examples/phase6_rx_pin_driver/
// uart_rx_pin_tb.v and examples/phase6_baud_error_coverage/
// uart_baud_cov_tb.v.  The duplication was deliberate: two benches that
// must agree about a measured tolerance limit are more convincing when a
// difference in their results cannot be a difference in their driver.
// That argument stops working at the third copy, and the Phase 4 UVM
// environment needed one.  So the driver became a module.
//
// THE ONE IDEA IN HERE
// --------------------
// The BFM's only timebase is `bit_ps`.  It never looks at the DUT's
// clock, never counts DUT clock cycles, and has no clock port at all.
// That is the whole point of an independent-timebase driver: a receiver
// whose stimulus is generated from its own clock cannot be tested for
// baud tolerance, because the mismatch under test is exactly the thing
// the shared clock removes.  The Phase 4 UVM driver it replaces advanced
// one bit with `for _ in range(BIT_CYCLES): await RisingEdge(dut.clk)`,
// which made every bit edge land on a DUT clock edge, every time, with
// zero edge-phase variation -- so that environment had never exercised
// the receiver's oversampling off-grid at all.
//
// WHY ps AND NOT ns-AS-REAL
// -------------------------
// `bit_ps` is a 32-bit integer in picoseconds rather than a `real` in
// nanoseconds, for two reasons that are about tooling rather than taste:
// a `real` module port is a portability hazard in Icarus, and cocotb
// cannot reliably write one.  A `#(real_ns)` delay inside a
// `timescale 1ns/1ps` module is already quantised to ps, so integer ps
// is not a loss of resolution -- but "already quantised to the same
// number" is a claim, so examples/phase6_bfm_equivalence/ measures it
// against a verbatim copy of the old task at ps resolution with zero
// tolerance, rather than asserting it here.  32 bits of ps is 4.29 ms,
// about 13000 nominal bit periods, which is far more headroom than any
// bench here needs.
//
// HANDSHAKE
// ---------
// Deliberately built from LEVEL waits, not edges, so the protocol is
// immune to delta-cycle ordering between the caller and the BFM and
// behaves identically whether the caller is a Verilog task or a cocotb
// coroutine:
//
//   caller: set mode/data/par/two_stop/bad_stop/bad_par/bit_ps/phase_ps
//           go = 1
//           wait (busy === 1)
//           go = 0
//           wait (busy === 0)
//
// `done_cnt` is provided as an alternative completion signal for callers
// that would rather poll a monotonically increasing value than watch a
// level -- which is the easier shape from Python, where "await until this
// changes" costs a clock-edge loop but "has this number moved" does not.
//
// `timescale is 1ps/1ps so that `#(bit_ps)` means picoseconds.  Mixing
// this with the 1ns/1ps DUT is fine and intended: each module's delays
// are interpreted in its own units, and $time in a 1ps module reports ps.

`timescale 1ps / 1ps

module uart_rx_pin_bfm (
    output reg         rx,        // the pin.  Idle high.
    input              go,
    output reg         busy,
    output reg [31:0]  done_cnt,  // increments once per completed action

    input      [1:0]   mode,
    input      [7:0]   data,
    input      [1:0]   par,       // 0 = none, 1 = even, 2 = odd
    input              two_stop,
    input              bad_stop,  // drive the FIRST stop bit low
    input              bad_par,   // invert an otherwise-correct parity bit
    input      [31:0]  bit_ps,    // THE timebase
    input      [31:0]  phase_ps,  // initial edge phase, before the start bit
    input      [31:0]  glitch_ps  // runt-pulse width, MODE_GLITCH only
);

    // Mode encoding.  MODE_IDLE exists so that a caller can consume a
    // gap through the same handshake it uses for everything else,
    // instead of holding the pin itself -- nothing outside this module
    // should ever drive `rx`.
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
    // The frame.  This is the old `drive_frame` task's body, unchanged
    // in structure, with `#(drv_bit_ns)` become `#(bit_ps)` and an
    // initial `#(phase_ps)` that the old `drive_phased` wrapper supplied
    // from outside.  Nothing here reads a clock.
    // -----------------------------------------------------------------
    task drive_frame_internal;
        integer i;
        reg p;
        begin
            if (phase_ps != 0) #(phase_ps);
            rx = 1'b0;                       // start bit
            #(bit_ps);
            for (i = 0; i < 8; i = i + 1) begin
                rx = data[i];                // LSB first
                #(bit_ps);
            end
            if (par != PAR_NONE) begin
                p = (par == PAR_EVEN) ? ^data : ~(^data);
                rx = bad_par ? ~p : p;
                #(bit_ps);
            end
            rx = bad_stop ? 1'b0 : 1'b1;     // stop 1
            #(bit_ps);
            if (two_stop) begin
                rx = 1'b1;                   // stop 2
                #(bit_ps);
            end
            rx = 1'b1;                       // return to idle
        end
    endtask

    // A runt low pulse, shorter than half a bit: the receiver's RX_START
    // mid-bit re-check must discard it.
    task drive_glitch_internal;
        begin
            if (phase_ps != 0) #(phase_ps);
            rx = 1'b0;
            #(glitch_ps);
            rx = 1'b1;
        end
    endtask

    // Hold idle for `bit_ps`.  A caller wanting n bits of gap issues n of
    // these, or one with bit_ps scaled -- both are exact, because the
    // only arithmetic is the caller's.
    task drive_idle_internal;
        begin
            rx = 1'b1;
            #(bit_ps);
        end
    endtask

    always begin
        wait (go === 1'b1);
        busy = 1'b1;
        case (mode)
            MODE_FRAME:  drive_frame_internal;
            MODE_GLITCH: drive_glitch_internal;
            MODE_IDLE:   drive_idle_internal;
            default: begin
                // An unknown mode is a caller bug and is reported rather
                // than silently treated as a frame.  A BFM that guesses
                // is a BFM whose failures are ambiguous.
                $display("** BFM ERROR: unknown mode %0d at t=%0t", mode, $time);
                rx = 1'b1;
            end
        endcase
        done_cnt = done_cnt + 32'd1;
        busy     = 1'b0;
        wait (go === 1'b0);
    end

endmodule
