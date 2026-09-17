// rtl/uart_controller.v
//
// UART controller with an APB-lite register interface, 8-entry TX/RX
// FIFOs and a level interrupt output.
//
// This is the v1 DUT specified by
// verification_plans/uart_controller_verification_plan.md (Section 1).
// It is written in Verilog-2001 (no SystemVerilog classes anywhere), so
// it compiles and simulates on this repo's pinned Icarus Verilog 10.3
// build -- the Icarus limitation documented since 2026-08-25 applies to
// class-based *testbenches*, not to synthesizable RTL.
//
// Scope follows the plan's Section 1.2 reductions exactly: 8 data bits
// fixed, pready tied high (no wait states), single clock domain (no CDC),
// no RTS/CTS flow control, no break/idle detection.
//
// Frame format: 1 start bit (0), 8 data bits LSB-first, optional parity
// (CTRL.parity_mode), 1 or 2 stop bits (CTRL.stop_bits), tx idle-high.
// Baud: a 16x-oversample tick every (BAUD_DIV+1) clk cycles, so one bit
// period is 16*(BAUD_DIV+1) clk cycles -> bit rate clk/(16*(div+1)),
// matching the plan's documented relationship.
//
// IMPLEMENTATION DECISION (deviation from the plan's Section 1 wording,
// flagged deliberately rather than applied silently): the plan calls
// STATUS "live status" for all seven bits. The three error bits
// (frame_err, parity_err, overrun_err) are implemented here as STICKY --
// set by the event, cleared by a STATUS read (the classic 16550 LSR
// read-to-clear behaviour) or by reset. A purely combinational "live"
// error bit would be asserted for only the single cycle the error is
// detected, which no register-interface read could reliably observe; the
// plan's own F4/F6 checks ("STATUS.parity_err is set exactly when ...",
// "overrun_err is set when ...") are only testable against a sticky bit.
// The four occupancy bits (tx_full, tx_empty, rx_full, rx_avail) ARE
// live/combinational as specified. This needs a vplan v2 revision
// (plan Section 7 explicitly anticipates exactly this kind of
// RTL-informed correction).

`timescale 1ns / 1ps

module uart_controller (
    input  wire       clk,
    input  wire       rst_n,

    // APB-lite register interface
    input  wire [3:0] paddr,
    input  wire [7:0] pwdata,
    output reg  [7:0] prdata,
    input  wire       pwrite,
    input  wire       psel,
    input  wire       penable,
    output wire       pready,

    // Serial lines
    output wire       tx,
    input  wire       rx,

    // Level interrupt, active high
    output wire       irq
);

    // ---------------------------------------------------------------
    // Register addresses (plan Section 1 register map)
    // ---------------------------------------------------------------
    localparam ADDR_CTRL     = 4'h0;
    localparam ADDR_STATUS   = 4'h1;
    localparam ADDR_BAUD_DIV = 4'h2;
    localparam ADDR_TX_DATA  = 4'h3;
    localparam ADDR_RX_DATA  = 4'h4;
    localparam ADDR_INT_EN   = 4'h5;

    localparam PARITY_NONE = 2'b00;
    localparam PARITY_EVEN = 2'b01;
    localparam PARITY_ODD  = 2'b10;

    assign pready = 1'b1;  // v1 scope: no wait states

    // APB access strobes (single-cycle access phase)
    wire acc     = psel & penable;
    wire wr_en   = acc &  pwrite;
    wire rd_en   = acc & ~pwrite;

    // ---------------------------------------------------------------
    // Programmable registers
    // ---------------------------------------------------------------
    reg [4:0] ctrl;       // [0] en, [2:1] parity_mode, [3] stop_bits, [4] loopback_en
    reg [7:0] baud_div;
    reg [2:0] int_en;     // [0] tx_empty_en, [1] rx_avail_en, [2] err_en

    wire       cfg_en        = ctrl[0];
    wire [1:0] cfg_parity    = ctrl[2:1];
    wire       cfg_two_stop  = ctrl[3];
    wire       cfg_loopback  = ctrl[4];

    // Sticky error flags (see IMPLEMENTATION DECISION above)
    reg frame_err, parity_err, overrun_err;

    // ---------------------------------------------------------------
    // TX FIFO (8 x 8, synchronous)
    // ---------------------------------------------------------------
    reg [7:0] tx_fifo [0:7];
    reg [2:0] tx_wptr, tx_rptr;
    reg [3:0] tx_cnt;
    wire tx_full  = (tx_cnt == 4'd8);
    wire tx_empty = (tx_cnt == 4'd0);

    // RX FIFO (8 x 8, synchronous)
    reg [7:0] rx_fifo [0:7];
    reg [2:0] rx_wptr, rx_rptr;
    reg [3:0] rx_cnt;
    wire rx_full  = (rx_cnt == 4'd8);
    wire rx_avail = (rx_cnt != 4'd0);

    // FIFO handshakes, resolved below by the TX/RX engines
    wire tx_push = wr_en & (paddr == ADDR_TX_DATA) & ~tx_full;  // full -> byte dropped
    reg  tx_pop;
    wire rx_pop  = rd_en & (paddr == ADDR_RX_DATA) & rx_avail;
    reg  rx_push;
    reg [7:0] rx_push_data;

    // ---------------------------------------------------------------
    // Baud generator: one 16x-oversample tick every (baud_div+1) cycles
    // ---------------------------------------------------------------
    reg [7:0] baud_cnt;
    wire os_tick = cfg_en & (baud_cnt == 8'd0);

    always @(posedge clk) begin
        if (!rst_n)          baud_cnt <= 8'd0;
        else if (!cfg_en)    baud_cnt <= 8'd0;
        else if (baud_cnt == 8'd0) baud_cnt <= baud_div;
        else                 baud_cnt <= baud_cnt - 8'd1;
    end

    // ---------------------------------------------------------------
    // TX engine
    // ---------------------------------------------------------------
    localparam TX_IDLE = 3'd0, TX_START = 3'd1, TX_DATA_S = 3'd2,
               TX_PAR  = 3'd3, TX_STOP1 = 3'd4, TX_STOP2  = 3'd5;

    reg [2:0] tx_state;
    reg [3:0] tx_os;       // 0..15 oversample position within a bit
    reg [2:0] tx_bit;      // which data bit
    reg [7:0] tx_shift;
    reg       tx_par_bit;
    reg       tx_line;

    wire tx_bit_done = os_tick & (tx_os == 4'd15);

    always @(posedge clk) begin
        if (!rst_n) begin
            tx_state <= TX_IDLE; tx_os <= 4'd0; tx_bit <= 3'd0;
            tx_shift <= 8'd0; tx_par_bit <= 1'b0; tx_line <= 1'b1;
            tx_pop <= 1'b0;
        end else begin
            tx_pop <= 1'b0;
            if (!cfg_en) begin
                tx_state <= TX_IDLE; tx_line <= 1'b1; tx_os <= 4'd0;
            end else begin
                if (os_tick) tx_os <= (tx_os == 4'd15) ? 4'd0 : tx_os + 4'd1;
                case (tx_state)
                    TX_IDLE: begin
                        tx_line <= 1'b1;
                        if (!tx_empty) begin
                            tx_shift   <= tx_fifo[tx_rptr];
                            tx_par_bit <= (cfg_parity == PARITY_EVEN) ?  ^tx_fifo[tx_rptr] :
                                          (cfg_parity == PARITY_ODD)  ? ~^tx_fifo[tx_rptr] : 1'b0;
                            tx_pop     <= 1'b1;
                            tx_state   <= TX_START;
                            tx_os      <= 4'd0;
                            tx_line    <= 1'b0;   // start bit
                        end
                    end
                    TX_START: begin
                        tx_line <= 1'b0;
                        if (tx_bit_done) begin
                            tx_state <= TX_DATA_S; tx_bit <= 3'd0;
                            tx_line  <= tx_shift[0];
                        end
                    end
                    TX_DATA_S: begin
                        tx_line <= tx_shift[tx_bit];
                        if (tx_bit_done) begin
                            if (tx_bit == 3'd7) begin
                                if (cfg_parity == PARITY_NONE) begin
                                    tx_state <= TX_STOP1; tx_line <= 1'b1;
                                end else begin
                                    tx_state <= TX_PAR;   tx_line <= tx_par_bit;
                                end
                            end else begin
                                tx_bit  <= tx_bit + 3'd1;
                                tx_line <= tx_shift[tx_bit + 3'd1];
                            end
                        end
                    end
                    TX_PAR: begin
                        tx_line <= tx_par_bit;
                        if (tx_bit_done) begin tx_state <= TX_STOP1; tx_line <= 1'b1; end
                    end
                    TX_STOP1: begin
                        tx_line <= 1'b1;
                        if (tx_bit_done) tx_state <= cfg_two_stop ? TX_STOP2 : TX_IDLE;
                    end
                    TX_STOP2: begin
                        tx_line <= 1'b1;
                        if (tx_bit_done) tx_state <= TX_IDLE;
                    end
                    default: tx_state <= TX_IDLE;
                endcase
            end
        end
    end

    assign tx = tx_line;

    // Loopback: internally route tx back to the receiver, ignoring the pin
    wire rx_in = cfg_loopback ? tx_line : rx;

    // ---------------------------------------------------------------
    // RX engine: 16x oversample, sample at mid-bit (os position 8)
    // ---------------------------------------------------------------
    localparam RX_IDLE = 3'd0, RX_START = 3'd1, RX_DATA_S = 3'd2,
               RX_PAR  = 3'd3, RX_STOP1 = 3'd4, RX_STOP2  = 3'd5;

    reg [2:0] rx_state;
    reg [3:0] rx_os;
    reg [2:0] rx_bit;
    reg [7:0] rx_shift;
    reg       rx_par_rcvd;
    reg       rx_sync;

    always @(posedge clk) begin
        if (!rst_n) rx_sync <= 1'b1;
        else        rx_sync <= rx_in;
    end

    wire rx_mid  = os_tick & (rx_os == 4'd8);
    wire rx_edge = os_tick & (rx_os == 4'd15);

    always @(posedge clk) begin
        if (!rst_n) begin
            rx_state <= RX_IDLE; rx_os <= 4'd0; rx_bit <= 3'd0;
            rx_shift <= 8'd0; rx_par_rcvd <= 1'b0;
            rx_push <= 1'b0; rx_push_data <= 8'd0;
            frame_err <= 1'b0; parity_err <= 1'b0; overrun_err <= 1'b0;
        end else begin
            rx_push <= 1'b0;

            // Sticky error bits clear on a STATUS read
            if (rd_en && (paddr == ADDR_STATUS)) begin
                frame_err <= 1'b0; parity_err <= 1'b0; overrun_err <= 1'b0;
            end

            if (!cfg_en) begin
                rx_state <= RX_IDLE; rx_os <= 4'd0;
            end else begin
                if (os_tick && rx_state != RX_IDLE)
                    rx_os <= (rx_os == 4'd15) ? 4'd0 : rx_os + 4'd1;

                case (rx_state)
                    RX_IDLE: begin
                        rx_os <= 4'd0;
                        if (!rx_sync) begin          // falling edge = candidate start
                            rx_state <= RX_START;
                            rx_os    <= 4'd0;
                        end
                    end
                    RX_START: begin
                        // Confirm the start bit is still low at mid-bit;
                        // otherwise it was a glitch, not a real frame.
                        if (rx_mid && rx_sync) rx_state <= RX_IDLE;
                        else if (rx_edge)      begin rx_state <= RX_DATA_S; rx_bit <= 3'd0; end
                    end
                    RX_DATA_S: begin
                        if (rx_mid) rx_shift[rx_bit] <= rx_sync;
                        if (rx_edge) begin
                            if (rx_bit == 3'd7)
                                rx_state <= (cfg_parity == PARITY_NONE) ? RX_STOP1 : RX_PAR;
                            else
                                rx_bit <= rx_bit + 3'd1;
                        end
                    end
                    RX_PAR: begin
                        if (rx_mid)  rx_par_rcvd <= rx_sync;
                        if (rx_edge) rx_state    <= RX_STOP1;
                    end
                    RX_STOP1: begin
                        if (rx_mid && !rx_sync) frame_err <= 1'b1;  // stop bit must be 1
                        if (rx_edge) begin
                            if (cfg_two_stop) begin
                                rx_state <= RX_STOP2;
                            end else begin
                                rx_state <= RX_IDLE;
                                // Parity check, then queue or flag overrun
                                if (cfg_parity != PARITY_NONE) begin
                                    if (rx_par_rcvd != ((cfg_parity == PARITY_EVEN) ? ^rx_shift : ~^rx_shift))
                                        parity_err <= 1'b1;
                                end
                                if (rx_full) overrun_err <= 1'b1;   // drop, do not overwrite
                                else begin rx_push <= 1'b1; rx_push_data <= rx_shift; end
                            end
                        end
                    end
                    RX_STOP2: begin
                        if (rx_mid && !rx_sync) frame_err <= 1'b1;
                        if (rx_edge) begin
                            rx_state <= RX_IDLE;
                            if (cfg_parity != PARITY_NONE) begin
                                if (rx_par_rcvd != ((cfg_parity == PARITY_EVEN) ? ^rx_shift : ~^rx_shift))
                                    parity_err <= 1'b1;
                            end
                            if (rx_full) overrun_err <= 1'b1;
                            else begin rx_push <= 1'b1; rx_push_data <= rx_shift; end
                        end
                    end
                    default: rx_state <= RX_IDLE;
                endcase
            end
        end
    end

    // ---------------------------------------------------------------
    // FIFO storage / pointers
    // ---------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            tx_wptr <= 3'd0; tx_rptr <= 3'd0; tx_cnt <= 4'd0;
        end else begin
            if (tx_push) begin tx_fifo[tx_wptr] <= pwdata; tx_wptr <= tx_wptr + 3'd1; end
            if (tx_pop)  tx_rptr <= tx_rptr + 3'd1;
            case ({tx_push, tx_pop})
                2'b10: tx_cnt <= tx_cnt + 4'd1;
                2'b01: tx_cnt <= tx_cnt - 4'd1;
                default: ;
            endcase
        end
    end

    always @(posedge clk) begin
        if (!rst_n) begin
            rx_wptr <= 3'd0; rx_rptr <= 3'd0; rx_cnt <= 4'd0;
        end else begin
            if (rx_push) begin rx_fifo[rx_wptr] <= rx_push_data; rx_wptr <= rx_wptr + 3'd1; end
            if (rx_pop)  rx_rptr <= rx_rptr + 3'd1;
            case ({rx_push, rx_pop})
                2'b10: rx_cnt <= rx_cnt + 4'd1;
                2'b01: rx_cnt <= rx_cnt - 4'd1;
                default: ;
            endcase
        end
    end

    // ---------------------------------------------------------------
    // Register writes
    // ---------------------------------------------------------------
    always @(posedge clk) begin
        if (!rst_n) begin
            ctrl <= 5'd0; baud_div <= 8'd0; int_en <= 3'd0;
        end else if (wr_en) begin
            case (paddr)
                ADDR_CTRL:     ctrl     <= pwdata[4:0];
                ADDR_BAUD_DIV: baud_div <= pwdata;
                ADDR_INT_EN:   int_en   <= pwdata[2:0];
                default: ;   // STATUS/RX_DATA writes ignored, TX_DATA handled by tx_push
            endcase
        end
    end

    // ---------------------------------------------------------------
    // Register reads
    // ---------------------------------------------------------------
    wire [7:0] status_val = {1'b0, overrun_err, parity_err, frame_err,
                             rx_avail, rx_full, tx_empty, tx_full};

    always @(*) begin
        case (paddr)
            ADDR_CTRL:     prdata = {3'b000, ctrl};
            ADDR_STATUS:   prdata = status_val;
            ADDR_BAUD_DIV: prdata = baud_div;
            ADDR_RX_DATA:  prdata = rx_fifo[rx_rptr];
            ADDR_INT_EN:   prdata = {5'b00000, int_en};
            // TX_DATA is write-only and undefined addresses read as 0:
            // an implementation-defined value, per the plan's Section 2.1
            // requirement that such a read must not hang or error.
            default:       prdata = 8'h00;
        endcase
    end

    // ---------------------------------------------------------------
    // Interrupt: OR of unmasked live conditions
    // ---------------------------------------------------------------
    assign irq = (tx_empty & int_en[0])
               | (rx_avail & int_en[1])
               | ((frame_err | parity_err | overrun_err) & int_en[2]);

endmodule
