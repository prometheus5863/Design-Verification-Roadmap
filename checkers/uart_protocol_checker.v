// checkers/uart_protocol_checker.v
//
// A BLACK-BOX PROTOCOL CHECKER for the uart_controller DUT.
//
// Phase 6 content item, created by the 2026-10-28 progress entry ("SVA
// protocol checkers bound into the UVM environment ... now the largest
// remaining block and unblocked").  Two deliberate departures from that
// wording, both forced and both recorded rather than glossed:
//
//  1. NOT SVA.  Icarus Verilog 10.3 -- this repository's pinned simulator,
//     installed by tools/setup_iverilog.sh -- does not support concurrent
//     assertions (`assert property`, sequences, `|->`, `$past`).  The rules
//     below are therefore written as PROCEDURAL monitors: clocked always
//     blocks that sample the interface and count violations.  That is a real
//     and common industry form (a protocol monitor / bus checker), it is
//     reusable in exactly the way an SVA checker is, and unlike SVA it runs
//     on the toolchain this repository actually has.  What is lost is the
//     declarative form and the automatic sequence bookkeeping; what is kept
//     is every rule.  The SVA form remains an open item against a simulator
//     that supports it.
//  2. NOT BOUND INTO THE UVM ENVIRONMENT YET.  This is the checker itself,
//     standalone and exercised by its own Verilog testbench, because the
//     checker has to be shown to have detection power BEFORE it is wired
//     into anything.  Wiring it into the uvm-python environment is a
//     separate, now-unblocked item.
//
// WHAT MAKES THIS DIFFERENT FROM THE RTL'S OWN FORMAL PROPERTIES.  The
// `FORMAL` blocks inside rtl/uart_controller.v are white-box: they refer to
// tx_state, baud_cnt, rx_cnt and other internals.  This checker refers to
// NOTHING but the module's pins.  It shadows the configuration by watching
// APB writes go past, so it would bind unchanged to a different
// implementation of the same register map -- which is the whole point of a
// protocol checker and is not true of a white-box property.
//
// FOURTEEN RULES, grouped.  Each has its own counter so that a mutation test
// can say WHICH rule caught a defect rather than only that something did.
//
//   A1  pready must be high in every access phase (v1 scope: no wait states)
//   A2  paddr/pwrite/pwdata must be stable while psel & penable
//   A3  penable must not be asserted without psel
//   A4  a read of an unmapped address must return 0x00
//   A5  prdata must be stable through a read access phase
//   R1  tx must be high while in reset
//   R2  irq must be low while in reset
//   T1  tx must be high when the shadow CTRL.en is 0
//   T2  the start bit must be low at its sampled centre
//   T3  the parity bit must match the parity of the eight sampled data bits
//   T4  every stop bit must be high at its sampled centre
//   T5  after the first bit boundary, every tx transition must fall on an
//       exact multiple of the bit period
//   T6  the start bit's length must lie in the window the oversampler can
//       produce (see the note on T6 below -- this rule is why T5 starts at
//       the FIRST BOUNDARY and not at the falling edge)
//   S1  a STATUS error bit read as set must read back clear on the next
//       STATUS read, if rx was idle throughout the interval (read-to-clear)
//   I1  irq must be low while the shadow INT_EN is 0
//
// THE T6 WINDOW, AND WHY IT IS A WINDOW.  The DUT leaves TX_IDLE the cycle
// it sees a non-empty TX FIFO, forcing tx_os to 0 and tx low immediately,
// WITHOUT waiting for the next oversample tick.  So the first of the start
// bit's sixteen oversample intervals is truncated by however much of
// baud_cnt was left: the start bit lasts between 15*(div+1)+1 and
// 16*(div+1) cycles, while every later bit lasts exactly 16*(div+1).  A
// checker that required the start bit to be a full bit period would fire on
// correct RTL.  The admissible window is therefore DERIVED from the
// oversampler, not loosened until green, and T6 pins both of its ends.  The
// truncation is at most one sixteenth of a bit, which is why centre-sampling
// from the falling edge is still safe: the worst-case drift (BITPER/16) is
// well inside the half-bit margin.
//
// The checker is Verilog-2001 with no classes, for the same reason the DUT
// is.

`timescale 1ns / 1ps

module uart_protocol_checker (
    input wire       clk,
    input wire       rst_n,
    input wire [3:0] paddr,
    input wire [7:0] pwdata,
    input wire [7:0] prdata,
    input wire       pwrite,
    input wire       psel,
    input wire       penable,
    input wire       pready,
    input wire       tx,
    input wire       rx,
    input wire       irq
);

    localparam ADDR_CTRL = 4'h0, ADDR_STATUS = 4'h1, ADDR_BAUD = 4'h2,
               ADDR_TXD  = 4'h3, ADDR_RXD    = 4'h4, ADDR_INTEN = 4'h5;

    localparam N_RULES = 14;
    localparam A1=0, A2=1, A3=2, A4=3, A5=4, R1=5, R2=6,
               T1=7, T2=8, T3=9, T4=10, T5=11, T6=12, S1=13;

    integer viol [0:N_RULES-1];
    integer fired [0:N_RULES-1];   // samples each rule actually evaluated
    reg     na    [0:N_RULES-1];   // not applicable in the DUT's v1 scope
    integer I1_IDX;                // kept as a name for readability below
    integer k;

    // Reported separately so a run can be shown to have EXERCISED a rule.
    // A rule with fired == 0 is a rule with no evidence either way, which is
    // the distinction this repository's 2026-10-28 entry called "a control
    // that has never fired is a control with no evidence that it can".

    initial begin
        for (k = 0; k < N_RULES; k = k + 1) begin
            viol[k]  = 0;
            fired[k] = 0;
            na[k]    = 1'b0;
        end
        // A2 and A5 are STRUCTURALLY UNEXERCISABLE against this DUT, and the
        // reason is derived from A1 rather than assumed: the plan's v1 scope
        // ties pready high (no wait states), A1 confirms it never goes low in
        // an access phase, and with pready always high an APB access phase is
        // exactly ONE cycle.  A2 ("signals stable WITHIN an access phase") and
        // A5 ("prdata stable WITHIN a read access phase") are statements about
        // a multi-cycle access phase that cannot occur.  They are kept in the
        // checker, not deleted, because they become live the moment the plan's
        // wait-state reduction is lifted -- and the testbench proves they can
        // still fire, by driving an illegal extended access phase as a planted
        // control.
        na[A2] = 1'b1;
        na[A5] = 1'b1;
        I1_IDX = 14;   // see note: I1 is counted in its own scalar below
    end

    integer viol_i1 = 0;
    integer fired_i1 = 0;

    task flag(input integer rule, input [511:0] msg);
    begin
        viol[rule] = viol[rule] + 1;
        $display("  CHECKER VIOLATION @%0t rule %0d: %0s", $time, rule, msg);
    end
    endtask

    // -----------------------------------------------------------------
    // Free-running cycle counter and edge registers
    // -----------------------------------------------------------------
    integer cyc = 0;
    always @(posedge clk) cyc = cyc + 1;

    // PAST_VALID.  At time 0 the DUT's outputs are X: its reset branch assigns
    // tx_line <= 1'b1 on the first posedge, so `tx` is only meaningful from
    // the SECOND edge onward.  Sampling on the first edge made R1 and R2 each
    // report one violation against correct RTL on this checker's first run.
    // The fix is the same device rtl/uart_controller.v's own FORMAL block uses
    // (`f_past_valid`): no rule evaluates until one edge has elapsed.  This is
    // an initialisation artefact of the sampler, not a relaxation -- no rule's
    // condition is weakened and no later cycle is skipped.
    reg past_valid = 1'b0;
    always @(posedge clk) past_valid <= 1'b1;

    reg tx_q = 1'b1;
    reg acc_q = 1'b0;
    reg [3:0] paddr_q;
    reg [7:0] pwdata_q, prdata_q;
    reg pwrite_q;

    wire acc = psel & penable;

    // -----------------------------------------------------------------
    // Shadow configuration, built only from observed APB writes
    // -----------------------------------------------------------------
    reg [4:0] sh_ctrl    = 5'd0;
    reg [7:0] sh_baud    = 8'd0;
    reg [2:0] sh_int_en  = 3'd0;

    wire       sh_en       = sh_ctrl[0];
    wire [1:0] sh_parity   = sh_ctrl[2:1];
    wire       sh_two_stop = sh_ctrl[3];

    always @(posedge clk) begin
        if (!rst_n) begin
            sh_ctrl <= 5'd0; sh_baud <= 8'd0; sh_int_en <= 3'd0;
        end else if (acc && pwrite && pready) begin
            case (paddr)
                ADDR_CTRL:  sh_ctrl   <= pwdata[4:0];
                ADDR_BAUD:  sh_baud   <= pwdata;
                ADDR_INTEN: sh_int_en <= pwdata[2:0];
                default: ;
            endcase
        end
    end

    // T1 needs the shadow to have been disabled for a FULL cycle before it
    // may demand tx high: the DUT drives tx_line from a clocked always block,
    // so the cycle in which CTRL.en is written still carries the old tx value.
    // One cycle of pipeline allowance, derived from the DUT being synchronous,
    // not a tolerance tuned until the rule went green.
    reg sh_en_q = 1'b0;
    always @(posedge clk) sh_en_q <= (rst_n ? sh_en : 1'b0);

    // One bit period in clk cycles, from the shadow divisor only.
    wire [31:0] bitper = 16 * (sh_baud + 1);

    // -----------------------------------------------------------------
    // A-group: the APB-lite rules
    // -----------------------------------------------------------------
    always @(posedge clk) begin
        if (rst_n && past_valid) begin
            if (acc) begin
                fired[A1] = fired[A1] + 1;
                if (pready !== 1'b1)
                    flag(A1, "pready low during an access phase");
            end
            if (penable && !psel) begin
                fired[A3] = fired[A3] + 1;
                flag(A3, "penable asserted without psel");
            end else if (penable || psel) begin
                fired[A3] = fired[A3] + 1;
            end
            if (acc && acc_q) begin
                fired[A2] = fired[A2] + 1;
                if (paddr !== paddr_q || pwrite !== pwrite_q)
                    flag(A2, "paddr/pwrite changed inside an access phase");
                else if (pwrite && pwdata !== pwdata_q)
                    flag(A2, "pwdata changed inside a write access phase");
                if (!pwrite) begin
                    fired[A5] = fired[A5] + 1;
                    if (prdata !== prdata_q)
                        flag(A5, "prdata changed inside a read access phase");
                end
            end
            if (acc && !pwrite && paddr > ADDR_INTEN) begin
                fired[A4] = fired[A4] + 1;
                if (prdata !== 8'h00)
                    flag(A4, "unmapped address did not read as 0x00");
            end
        end
        acc_q    <= acc;
        paddr_q  <= paddr;
        pwrite_q <= pwrite;
        pwdata_q <= pwdata;
        prdata_q <= prdata;
    end

    // -----------------------------------------------------------------
    // R-group: reset
    // -----------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n && past_valid) begin
            fired[R1] = fired[R1] + 1;
            fired[R2] = fired[R2] + 1;
            if (tx !== 1'b1)  flag(R1, "tx not high during reset");
            if (irq !== 1'b0) flag(R2, "irq not low during reset");
        end
    end

    // -----------------------------------------------------------------
    // T-group: the serial frame
    // -----------------------------------------------------------------
    reg         mon_active = 1'b0;
    integer     t_fall;          // cycle of the start-bit falling edge
    integer     t_boundary;      // cycle of the first bit boundary seen
    reg         have_boundary = 1'b0;
    integer     samp_next;       // cycle of the next centre sample
    integer     samp_idx;        // 0 = start, 1..8 = data, then parity/stop
    integer     n_samples;       // total centre samples this frame
    integer     bp_lat;          // bit period latched at frame start
    reg  [7:0]  data_acc;
    reg         par_expect;
    integer     frames = 0;
    integer     aborted = 0;   // frames abandoned because CTRL.en went 0
    integer     lost = 0;      // frames abandoned by the watchdog

    // The start bit's measurable length needs a rising edge right after it,
    // i.e. a frame whose LSB is 1.  Frames with LSB 0 cannot exercise T6 and
    // are not counted as evidence for it.
    integer t6_frames = 0;   // frames with a measurable start bit
    integer t6_max = 0;      // worst truncation seen, in clk cycles

    always @(posedge clk) begin
        if (!rst_n) begin
            mon_active    <= 1'b0;
            have_boundary <= 1'b0;
        end else if (past_valid) begin
            // T1: line must idle high whenever the shadow says disabled
            if (!sh_en && !sh_en_q) begin
                fired[T1] = fired[T1] + 1;
                if (tx !== 1'b1)
                    flag(T1, "tx not high while shadow CTRL.en is 0");
            end

            // ABORT PATH.  Found by a real failure, not by inspection: the
            // 9b stimulus disables the DUT mid-frame, and without this branch
            // the monitor stayed armed on a frame that never completed, never
            // re-armed, and judged three LATER frames against the dead frame's
            // bit grid -- 16 spurious T5 violations and one T6 on correct RTL.
            // A frame terminated by CTRL.en going low is not a protocol
            // violation; it is a frame that stops existing, and the monitor
            // has to be able to say so.
            if (mon_active && !sh_en) begin
                mon_active <= 1'b0;
                aborted = aborted + 1;
            end
            // WATCHDOG.  Defensive, and for the same reason: any path that
            // leaves the monitor armed poisons every later frame silently.
            // A frame cannot outlast its own sample schedule by two bits.
            else if (mon_active &&
                     (cyc - t_fall) > ((n_samples + 2) * bp_lat)) begin
                mon_active <= 1'b0;
                lost = lost + 1;
                $display("  [checker] frame %0d abandoned by the watchdog after %0d cycles",
                         frames, cyc - t_fall);
            end
            // frame start
            else if (!mon_active && sh_en && tx_q === 1'b1 && tx === 1'b0) begin
                mon_active    <= 1'b1;
                have_boundary <= 1'b0;
                t_fall        =  cyc;
                bp_lat        =  bitper;
                samp_idx      =  0;
                samp_next     =  cyc + (bitper / 2);
                data_acc      <= 8'h00;
                n_samples     =  1 + 8 + ((sh_parity == 2'b00) ? 0 : 1)
                                       + (sh_two_stop ? 2 : 1);
                frames        =  frames + 1;
            end else if (mon_active) begin
                // first boundary after the start bit, for T5's origin and T6
                if (!have_boundary && tx !== tx_q) begin
                    have_boundary <= 1'b1;
                    t_boundary    =  cyc;
                    fired[T6] = fired[T6] + 1;
                    if ((cyc - t_fall) > bp_lat ||
                        (cyc - t_fall) < (bp_lat - (bp_lat / 16))) begin
                        flag(T6, "start bit outside the oversampler window");
                        $display("         measured %0d cycles, window [%0d, %0d]",
                                 cyc - t_fall, bp_lat - (bp_lat / 16), bp_lat);
                    end
                    // Track the TRUNCATION, not the raw length: raw lengths
                    // from two different divisors are not comparable, and the
                    // quantity the T6 window is about is bitper - measured.
                    if ((bp_lat - (cyc - t_fall)) > t6_max)
                        t6_max = bp_lat - (cyc - t_fall);
                    t6_frames = t6_frames + 1;        // frames with a measurement
                    $display("  [checker] frame %0d: start bit %0d cycles, bit period %0d, truncation %0d",
                             frames, cyc - t_fall, bp_lat,
                             bp_lat - (cyc - t_fall));
                end else if (have_boundary && tx !== tx_q) begin
                    // T5: every later transition is a whole number of bits
                    fired[T5] = fired[T5] + 1;
                    if (((cyc - t_boundary) % bp_lat) != 0) begin
                        flag(T5, "tx transition off the bit grid");
                        $display("         %0d cycles after first boundary, bit period %0d, remainder %0d",
                                 cyc - t_boundary, bp_lat,
                                 (cyc - t_boundary) % bp_lat);
                    end
                end

                // centre samples
                if (cyc == samp_next) begin
                    if (samp_idx == 0) begin
                        fired[T2] = fired[T2] + 1;
                        if (tx !== 1'b0)
                            flag(T2, "start bit not low at its centre");
                    end else if (samp_idx <= 8) begin
                        data_acc[samp_idx-1] <= tx;
                    end else if (samp_idx == 9 && sh_parity != 2'b00) begin
                        fired[T3] = fired[T3] + 1;
                        par_expect = (sh_parity == 2'b01) ? ^data_acc
                                                          : ~(^data_acc);
                        if (tx !== par_expect) begin
                            flag(T3, "parity bit does not match the data");
                            $display("         data 0x%02h, mode %0d, expected %0b, saw %0b",
                                     data_acc, sh_parity, par_expect, tx);
                        end
                    end else begin
                        fired[T4] = fired[T4] + 1;
                        if (tx !== 1'b1)
                            flag(T4, "stop bit not high at its centre");
                    end

                    samp_idx  = samp_idx + 1;
                    samp_next = samp_next + bp_lat;
                    if (samp_idx >= n_samples) mon_active <= 1'b0;
                end
            end
        end
        tx_q <= tx;
    end

    // -----------------------------------------------------------------
    // S1: the sticky error bits must be read-to-clear
    // -----------------------------------------------------------------
    // The RTL implements STATUS[6:4] (overrun, parity, frame) as sticky,
    // cleared by a STATUS read -- a deliberate deviation from the v1 plan's
    // "live status" wording, flagged in the RTL header and needing a vplan
    // v2 revision.  This rule is the executable form of the v2 wording: an
    // error bit seen set must be clear on the next STATUS read, PROVIDED rx
    // stayed idle in between (a new frame could legitimately re-set it).
    reg [2:0] last_err = 3'b000;
    reg       have_last = 1'b0;
    reg       rx_quiet = 1'b1;
    reg       status_rd_q = 1'b0;
    wire      status_rd = acc & ~pwrite & (paddr == ADDR_STATUS);

    always @(posedge clk) begin
        if (!rst_n) begin
            have_last <= 1'b0; rx_quiet <= 1'b1; last_err <= 3'b000;
        end else if (past_valid) begin
            if (rx !== 1'b1) rx_quiet <= 1'b0;
            // sample the read on the FIRST cycle of the access phase only
            if (status_rd && !status_rd_q) begin
                if (have_last && rx_quiet) begin
                    fired[S1] = fired[S1] + 1;
                    if ((prdata[6:4] & last_err) != 3'b000) begin
                        flag(S1, "sticky error bit survived a STATUS read");
                        $display("         previous %03b, now %03b, rx idle throughout",
                                 last_err, prdata[6:4]);
                    end
                end
                last_err  <= prdata[6:4];
                have_last <= 1'b1;
                rx_quiet  <= (rx === 1'b1);
            end
        end
        status_rd_q <= status_rd;
    end

    // -----------------------------------------------------------------
    // I1: irq must be low while nothing is enabled
    // -----------------------------------------------------------------
    always @(posedge clk) begin
        if (rst_n && past_valid && sh_int_en == 3'b000) begin
            fired_i1 = fired_i1 + 1;
            if (irq !== 1'b0) begin
                viol_i1 = viol_i1 + 1;
                $display("  CHECKER VIOLATION @%0t rule I1: irq high while shadow INT_EN is 0",
                         $time);
            end
        end
    end

    // -----------------------------------------------------------------
    // Reporting
    // -----------------------------------------------------------------
    function [511:0] rule_name(input integer r);
        case (r)
            0: rule_name = "A1 pready high in access phase";
            1: rule_name = "A2 address/data stable in access";
            2: rule_name = "A3 penable implies psel";
            3: rule_name = "A4 unmapped read is 0x00";
            4: rule_name = "A5 prdata stable in read access";
            5: rule_name = "R1 tx high in reset";
            6: rule_name = "R2 irq low in reset";
            7: rule_name = "T1 tx high when disabled";
            8: rule_name = "T2 start bit low at centre";
            9: rule_name = "T3 parity matches data";
           10: rule_name = "T4 stop bits high at centre";
           11: rule_name = "T5 transitions on the bit grid";
           12: rule_name = "T6 start bit in oversampler window";
           13: rule_name = "S1 error bits are read-to-clear";
            default: rule_name = "??";
        endcase
    endfunction

    function integer rule_viol(input integer r);
        rule_viol = viol[r];
    endfunction

    task report(output integer total_viol, output integer unexercised);
        integer r;
    begin
        total_viol  = 0;
        unexercised = 0;
        $display("");
        $display("  ---- protocol checker: %0d rules, %0d frames monitored ----",
                 N_RULES + 1, frames);
        $display("  %-40s %10s %10s", "rule", "evaluated", "violations");
        for (r = 0; r < N_RULES; r = r + 1) begin
            if (na[r])
                $display("  %-40s %10d %10d   (N/A in v1 scope)",
                         rule_name(r), fired[r], viol[r]);
            else
                $display("  %-40s %10d %10d", rule_name(r), fired[r], viol[r]);
            total_viol = total_viol + viol[r];
            if (fired[r] == 0 && !na[r]) unexercised = unexercised + 1;
        end
        $display("  %-40s %10d %10d", "I1 irq low when masked",
                 fired_i1, viol_i1);
        total_viol = total_viol + viol_i1;
        if (fired_i1 == 0) unexercised = unexercised + 1;
        $display("  frames: %0d started, %0d aborted by a disable, %0d lost to the watchdog",
                 frames, aborted, lost);
        $display("  start-bit truncation: %0d frames measured, worst %0d cycles",
                 t6_frames, t6_max);
        $display("  (T6's window is [bitper - bitper/16, bitper], i.e. a truncation");
        $display("   of at most bitper/16 = div+1 cycles.  A worst case EQUAL to");
        $display("   bitper/16 means the derived bound is attained and therefore");
        $display("   tight: one cycle looser would be slack, one cycle tighter");
        $display("   would fail on correct RTL.  A worst case of 0 would mean the");
        $display("   lower end of the window has no evidence at all.)");
        $display("  ---- total violations %0d, unexercised rules %0d ----",
                 total_viol, unexercised);
    end
    endtask

endmodule
