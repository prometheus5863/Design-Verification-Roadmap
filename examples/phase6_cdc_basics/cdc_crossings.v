// examples/phase6_cdc_basics/cdc_crossings.v
//
// Synthesisable clock-domain-crossing primitives, Phase 6 "CDC
// verification basics".  Nothing in this file is a modelling artefact:
// every module here is something you would actually put in RTL.  The
// per-bit skew that makes the multi-bit bug VISIBLE lives in the
// testbench, because it is a model of physical reality and not design
// intent -- see notes/2026-11-10-cdc-*.md Section 3.
//
// Verilog-2001 compatible (Icarus Verilog 10.3 is the toolchain here, and
// its SystemVerilog support is partial).

`default_nettype none

// ---------------------------------------------------------------------
// Two-flop synchroniser.  The standard answer to "how do you cross a
// single-bit signal".  Width-parameterised ON PURPOSE even though using
// it on W>1 is the classic bug: the testbench needs to instantiate the
// wrong thing to show that it is wrong.
// ---------------------------------------------------------------------
module cdc_sync_2ff #(parameter W = 1) (
    input  wire         clk_dst,
    input  wire         rst_n,
    input  wire [W-1:0] d_src,
    output wire [W-1:0] q_dst
);
    reg [W-1:0] ff1, ff2;
    always @(posedge clk_dst or negedge rst_n) begin
        if (!rst_n) begin
            ff1 <= {W{1'b0}};
            ff2 <= {W{1'b0}};
        end else begin
            ff1 <= d_src;
            ff2 <= ff1;
        end
    end
    assign q_dst = ff2;
endmodule


// ---------------------------------------------------------------------
// Binary <-> Gray.  Gray coding is what makes a multi-bit crossing safe
// WITHOUT a handshake: successive values differ in exactly one bit, so
// any per-bit sampling skew can only yield the old value or the new one,
// never a third value that was never held.
// ---------------------------------------------------------------------
module bin2gray #(parameter W = 8) (
    input  wire [W-1:0] bin,
    output wire [W-1:0] gray
);
    assign gray = bin ^ (bin >> 1);
endmodule

module gray2bin #(parameter W = 8) (
    input  wire [W-1:0] gray,
    output wire [W-1:0] bin
);
    // bin[W-1] = gray[W-1];  bin[i] = bin[i+1] ^ gray[i]
    // i.e. bin[i] = XOR of gray[W-1:i]  -- written as the reduction so it
    // is a single expression rather than a loop Icarus must unroll.
    reg [W-1:0] b;
    integer i;
    always @(*) begin
        b[W-1] = gray[W-1];
        for (i = W-2; i >= 0; i = i - 1)
            b[i] = b[i+1] ^ gray[i];
    end
    assign bin = b;
endmodule


// ---------------------------------------------------------------------
// Pulse crossing, source half: convert a possibly-narrow pulse in the
// source domain into a LEVEL TOGGLE, which survives being sampled by any
// slower clock because it never returns to its old value.
// ---------------------------------------------------------------------
module cdc_pulse_toggle_src (
    input  wire clk_src,
    input  wire rst_n,
    input  wire pulse_src,
    output reg  toggle_src
);
    always @(posedge clk_src or negedge rst_n) begin
        if (!rst_n)          toggle_src <= 1'b0;
        else if (pulse_src)  toggle_src <= ~toggle_src;
    end
endmodule


// ---------------------------------------------------------------------
// Pulse crossing, destination half: synchronise the toggle and convert
// each edge back into a one-clk_dst-wide pulse.
// ---------------------------------------------------------------------
module cdc_pulse_toggle_dst (
    input  wire clk_dst,
    input  wire rst_n,
    input  wire toggle_src,
    output wire pulse_dst
);
    wire sync_q;
    reg  sync_q_d;

    cdc_sync_2ff #(.W(1)) u_sync (
        .clk_dst (clk_dst),
        .rst_n   (rst_n),
        .d_src   (toggle_src),
        .q_dst   (sync_q)
    );

    always @(posedge clk_dst or negedge rst_n) begin
        if (!rst_n) sync_q_d <= 1'b0;
        else        sync_q_d <= sync_q;
    end

    assign pulse_dst = sync_q ^ sync_q_d;
endmodule

`default_nettype wire
