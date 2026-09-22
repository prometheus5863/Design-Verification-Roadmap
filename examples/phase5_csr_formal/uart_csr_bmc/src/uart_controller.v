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


`ifdef FORMAL
    // ===============================================================
    // Formal property block (Phase 5, 2026-09-20).
    //
    // Guarded by `ifdef FORMAL so that this file is BIT-IDENTICAL to the
    // Phase 4 DUT under Icarus: nothing here is compiled by
    // examples/phase4_*/ regressions. That claim is checked, not asserted
    // -- examples/phase5_formal_uart/run_formal.sh re-runs the 60-check
    // Phase 4 regression and requires 60/60.
    //
    // Scope: the TX and RX FIFO control paths. Chosen because their
    // correctness is an UNBOUNDED claim -- "the count never exceeds 8, for
    // any trace of any length" -- which is exactly the class of property
    // simulation cannot establish and k-induction can. The serial
    // datapath is deliberately NOT covered here; see the notes file for
    // why (its properties need multi-bit-period sequences, and the WASM
    // solver budget does not reach them).
    //
    // Conventions follow the SymbiYosys idiom: properties are disabled
    // during reset via f_past_valid, and assume() constrains the
    // environment, assert() states the obligation.
    // ===============================================================
    reg f_past_valid = 1'b0;
    always @(posedge clk) f_past_valid <= 1'b1;

    // ENVIRONMENT ASSUMPTION. Without this the solver starts the trace
    // mid-flight in an arbitrary state and every property below is
    // trivially falsifiable -- which is a statement about the assumption,
    // not about the design.
    always @(*)
        if (!f_past_valid) assume(!rst_n);

    // ---- P1: the FIFO counts never leave their legal range ----------
    // Pure safety. Inductive on its own: both pushes are guarded by
    // ~full and both pops by non-empty.
    always @(posedge clk)
        if (f_past_valid && rst_n) begin
            assert(tx_cnt <= 4'd8);
            assert(rx_cnt <= 4'd8);
        end

    // ---- P2: pointer/count consistency -------------------------------
    // The real invariant. A 3-bit pointer difference must equal the
    // 4-bit count modulo 8 at all times; this is what makes the occupancy
    // flags meaningful, and it is NOT implied by P1.
    always @(posedge clk)
        if (f_past_valid && rst_n) begin
            assert((tx_wptr - tx_rptr) == tx_cnt[2:0]);
            assert((rx_wptr - rx_rptr) == rx_cnt[2:0]);
        end

    // ---- P3: the occupancy flags are mutually consistent -------------
    // full and empty can never both hold. Follows from P1, and is stated
    // separately because it is the flag a testbench actually reads.
    always @(posedge clk)
        if (f_past_valid && rst_n) begin
            assert(!(tx_full && tx_empty));
            assert(!(rx_full && rx_avail == 1'b0 && rx_cnt != 4'd0));
        end

    // ---- P4: no silent overflow or underflow -------------------------
    // The count may only change by one per cycle, and only in the
    // direction the strobes call for. This is the property that a
    // mutated push/pop guard breaks.
    always @(posedge clk)
        if (f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)) begin
            assert(tx_cnt == $past(tx_cnt)
                   || tx_cnt == $past(tx_cnt) + 4'd1
                   || tx_cnt == $past(tx_cnt) - 4'd1);
            assert(!($past(tx_full) && !$past(tx_pop) && tx_cnt > $past(tx_cnt)));
            assert(!($past(tx_empty) && !$past(tx_push) && tx_cnt < $past(tx_cnt)));
        end

    // ---- C1: cover, to prove the properties are not vacuous ----------
    // A passing assertion set on a design that can never fill a FIFO
    // would be worthless. These require the solver to EXHIBIT a full TX
    // FIFO and a wrapped pointer.
    always @(posedge clk)
        if (f_past_valid && rst_n) begin
            cover(tx_cnt == 4'd8);
            cover(tx_rptr != 3'd0 && tx_cnt == 4'd0);
        end

    // ===============================================================
    // CSR property block (Phase 5, 2026-09-21).
    //
    // Nested under a SECOND define on purpose. The 2026-09-20 FIFO jobs
    // compile with -DFORMAL only, so they see exactly the source they saw
    // then and that session's bmc/prove/cover/mutation numbers stay
    // bit-reproducible. The CSR jobs pass -DFORMAL -DFORMAL_CSR.
    //
    // Scope: the six-register APB map -- write/read-back, decode
    // isolation, reserved bits, the read mux, the live STATUS bits, the
    // sticky-error read-to-clear path, RX_DATA pop-on-read, and interrupt
    // masking. These are SHALLOW properties: every one of them is decided
    // within a couple of cycles, which is what BMC is good at and is why
    // 2026-09-20 named this the next target rather than the serial
    // datapath.
    //
    // HONEST CLASSIFICATION, because not all of these are worth the same.
    //   STRUCTURAL RESTATEMENT (weakest): C3, C4. These restate the read
    //     mux. A mutation of that mux is detected trivially, because the
    //     property and the logic are the same sentence written twice.
    //     They are kept because they are the register map's spec and they
    //     fire on an address-decode change that breaks many things at once.
    //   CROSS-CHECK (what the suite is actually for): C1, C2, C5, C6, C7,
    //     C8, C9. Each relates one part of the design to a DIFFERENT part
    //     -- a write port to a read port, a flag to the FIFO that drives
    //     it, a clear path to the FSM that sets it -- so no single line of
    //     RTL can make one true by construction.
    // ===============================================================
`ifdef FORMAL_CSR
    wire f_csr_wr   = wr_en;
    wire f_csr_rd   = rd_en;
    wire f_rx_stopping = (rx_state == RX_STOP1) || (rx_state == RX_STOP2);

    // ---- C1: write / read-back on the three RW registers -------------
    // CROSS-CHECK: relates the write decoder to the register state one
    // cycle later. Note baud_div takes all 8 bits while ctrl takes 5 and
    // int_en takes 3 -- a width mutation is exactly what this catches.
    always @(posedge clk)
        if (f_past_valid && rst_n && $past(rst_n) && $past(f_csr_wr)) begin
            if ($past(paddr) == ADDR_CTRL)     assert(ctrl     == $past(pwdata[4:0]));
            if ($past(paddr) == ADDR_BAUD_DIV) assert(baud_div == $past(pwdata));
            if ($past(paddr) == ADDR_INT_EN)   assert(int_en   == $past(pwdata[2:0]));
        end

    // ---- C2: decode isolation -- no write aliasing --------------------
    // CROSS-CHECK, and the strongest property here. Stated in the
    // contrapositive: a register that CHANGED must have been addressed.
    // This covers, in one line each, every "a write to STATUS / RX_DATA /
    // an unmapped address must not disturb anything" requirement, without
    // enumerating the sixteen addresses.
    always @(posedge clk)
        if (f_past_valid && rst_n && $past(rst_n)) begin
            if (ctrl     != $past(ctrl))
                assert($past(f_csr_wr) && $past(paddr) == ADDR_CTRL);
            if (baud_div != $past(baud_div))
                assert($past(f_csr_wr) && $past(paddr) == ADDR_BAUD_DIV);
            if (int_en   != $past(int_en))
                assert($past(f_csr_wr) && $past(paddr) == ADDR_INT_EN);
        end

    // ---- C3: read mux and reserved bits (STRUCTURAL RESTATEMENT) ------
    always @(*)
        if (f_past_valid && rst_n) begin
            if (paddr == ADDR_CTRL)     assert(prdata == {3'b000, ctrl});
            if (paddr == ADDR_BAUD_DIV) assert(prdata == baud_div);
            if (paddr == ADDR_INT_EN)   assert(prdata == {5'b00000, int_en});
            if (paddr == ADDR_STATUS)   assert(prdata[7] == 1'b0);
        end

    // ---- C4: write-only and unmapped reads (STRUCTURAL RESTATEMENT) ---
    // TX_DATA is write-only; 4'h6..4'hF are unmapped. The plan requires
    // such a read to return a defined value and not hang.
    always @(*)
        if (f_past_valid && rst_n)
            if (paddr == ADDR_TX_DATA || paddr > ADDR_INT_EN)
                assert(prdata == 8'h00);

    // ---- C5: the four LIVE status bits track the FIFOs exactly --------
    // CROSS-CHECK, and the one that settles a verification-plan wording
    // question raised on 2026-09-17. The plan calls STATUS "live". For
    // bits [3:0] that is exactly true and is proved here; for the three
    // error bits it is false by construction, and C6 states what holds
    // instead. The plan's single word covered two different contracts.
    always @(*)
        if (f_past_valid && rst_n && paddr == ADDR_STATUS) begin
            assert(prdata[0] == tx_full);
            assert(prdata[1] == tx_empty);
            assert(prdata[2] == rx_full);
            assert(prdata[3] == rx_avail);
        end

    // ---- C6: the sticky error bits are read-to-clear ------------------
    // CROSS-CHECK. A STATUS read must clear all three error bits -- UNLESS
    // the RX engine is in a stop state that same cycle, where the set path
    // legitimately wins over the clear (last assignment in the block).
    //
    // The exception is stated in terms of rx_state ONLY, deliberately: if
    // it duplicated the set CONDITIONS (rx_mid && !rx_sync, the parity
    // compare, rx_full) the property would be the set logic written twice
    // and a mutation of that logic would make property and design wrong
    // together. Naming only the state keeps the two independent.
    always @(posedge clk)
        if (f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)
            && $past(f_csr_rd) && $past(paddr) == ADDR_STATUS
            && !$past(f_rx_stopping)) begin
            assert(!frame_err);
            assert(!parity_err);
            assert(!overrun_err);
        end

    // ---- C7: the error bits can only RISE in a stop state -------------
    // CROSS-CHECK on the same path from the other side. Together with C6
    // this pins the sticky bits down completely: they rise only in a stop
    // state and fall only on a STATUS read.
    always @(posedge clk)
        if (f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)) begin
            if (frame_err   && !$past(frame_err))   assert($past(f_rx_stopping));
            if (parity_err  && !$past(parity_err))  assert($past(f_rx_stopping));
            if (overrun_err && !$past(overrun_err)) assert($past(f_rx_stopping));
        end

    // ---- C8: RX_DATA pop-on-read, and no pop when empty ---------------
    // CROSS-CHECK: relates an APB read to FIFO occupancy. The second half
    // is the one that matters -- a read of an empty RX FIFO must not move
    // the pointer, which is the classic read-side underflow bug.
    always @(posedge clk)
        if (f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)) begin
            if ($past(f_csr_rd) && $past(paddr) == ADDR_RX_DATA && $past(rx_avail))
                assert(rx_cnt == $past(rx_cnt) - 4'd1 || $past(rx_push));
            if ($past(f_csr_rd) && $past(paddr) == ADDR_RX_DATA && !$past(rx_avail)) begin
                assert(rx_rptr == $past(rx_rptr));
                assert(rx_cnt  == $past(rx_cnt) + ($past(rx_push) ? 4'd1 : 4'd0));
            end
        end

    // ---- C9: interrupt masking ----------------------------------------
    // CROSS-CHECK, stated so that it is NOT the irq assign written twice:
    // a fully masked interrupt controller must be silent, whatever the
    // FIFOs and error bits are doing.
    always @(*)
        if (f_past_valid && rst_n) begin
            if (int_en == 3'd0) assert(!irq);
            if (irq)            assert(int_en != 3'd0);
        end

    // ---- C10: covers -- the CSR suite must not be vacuous -------------
    //
    // EVERY cover here is guarded by $past(rst_n) as well as rst_n. That
    // is not boilerplate; it is a fix for a defect this suite shipped with
    // for exactly one run.
    //
    // THE BUG (2026-09-21, found by reading the trace of a PASS):
    //   cover(f_csr_rd && paddr == ADDR_STATUS && $past(overrun_err));
    // guarded only by (f_past_valid && rst_n) was reported REACHED at the
    // first opportunity. The witness trace showed why: at step 0 the
    // solver is free to choose overrun_err = 1, because the design has a
    // SYNCHRONOUS reset and step 0 is before the first clock edge. One
    // cycle later rst_n is high and the design is reset -- but $past()
    // still reaches BACK ACROSS THE RESET BOUNDARY and returns the
    // pre-reset garbage. The cover fired on a value the design had already
    // thrown away.
    //
    // This matters more than a mis-scored cover. The cover's whole job was
    // to show that C6 (read-to-clear) is not vacuous. It "passed" without
    // the design ever setting an error bit, so it demonstrated nothing --
    // a green light that certified its own uselessness.
    //
    // Note the assertions C1-C9 were NOT affected: every one that uses
    // $past is guarded by $past(rst_n), so none of them can read across
    // the boundary. The covers were the only place the guard was missing,
    // which is the easy place to forget it.
    //
    // See examples/phase5_csr_formal/README.md for the trace.
    always @(posedge clk)
        if (f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)) begin
            // c1: the interrupt can actually assert
            cover(irq);
            // c2: a read of an EMPTY RX FIFO -- the state C8's second
            //     branch is about, so C8 is not vacuous
            cover(f_csr_rd && paddr == ADDR_RX_DATA && !rx_avail);
            // c3: an access to an unmapped address -- C2's and C4's state
            cover(f_csr_wr && paddr > ADDR_INT_EN);
            // c4: a STATUS read at all -- C6's antecedent
            cover(f_csr_rd && paddr == ADDR_STATUS);
            // c5: a write and a read of CTRL in consecutive cycles --
            //     C1's antecedent followed by C3's
            cover(f_csr_rd && paddr == ADDR_CTRL
                  && $past(f_csr_wr) && $past(paddr) == ADDR_CTRL);
        end

    // ---- C11: DEEP cover, separate job ---------------------------------
    // C6's non-vacuity needs an error bit that the DESIGN set, which needs
    // a complete serial frame: a start bit plus eight data bits plus a
    // stop bit at sixteen oversample ticks each. With baud_div free that is
    // unbounded; even at baud_div = 0 it is ~160 clocks, far past the depth
    // the shallow job runs at. This block assumes the fastest legal baud
    // and is run as its own job at high depth, so that the cost lands in
    // one place and the shallow job stays fast.
    //
    // Whatever this job returns is reported as measured. An unreached
    // cover here is a statement about the solver budget, NOT a claim that
    // the design cannot set an error bit -- the Phase 4 simulation
    // regression sets all three of them every run.
`ifdef FORMAL_CSR_DEEP
    always @(*) assume(baud_div == 8'd0);
    always @(posedge clk)
        if (f_past_valid && $past(f_past_valid) && rst_n && $past(rst_n)) begin
            cover(rx_state == RX_STOP1);
            cover(frame_err);
            cover(f_csr_rd && paddr == ADDR_STATUS && $past(frame_err));
        end
`endif
`endif
`endif


`ifdef FORMAL_CSR_RESET
    // ===============================================================
    // RESET-VALUE PROPERTIES (Phase 5, day 3, 2026-09-22)
    //
    // This block closes the item 2026-09-21 created and named as the
    // natural next one: "reset-value properties are unchecked."
    //
    // WHY THEY WERE MISSING, AND WHY THE GUARD IS INVERTED.
    // Every property in `FORMAL and `FORMAL_CSR is guarded by
    // (f_past_valid && rst_n): disabled during reset, by design, because
    // a property about steady-state behaviour has nothing to say while
    // the design is being forced to a known state. That guard is exactly
    // what makes reset values unreachable -- the one obligation of the
    // seven CSR obligations whose whole content lives inside the window
    // every other property excludes.
    //
    // The correct guard is its MIRROR IMAGE: sample on the first edge
    // AFTER a cycle in which rst_n was low.
    //
    //     f_past_valid && !$past(rst_n)     <- here
    //     f_past_valid &&  rst_n            <- everywhere else
    //
    // $past() is safe here for the reason it was NOT safe on 2026-09-21:
    // f_past_valid guarantees at least one edge has elapsed, so $past()
    // reads a value the design actually held, and the value it reads is
    // rst_n itself rather than state the reset has since discarded. The
    // 2026-09-21 hazard was reading STATE across a reset boundary; reading
    // the RESET SIGNAL across that boundary is the whole point.
    //
    // This is a synchronous reset, so the obligation is "one edge after
    // rst_n was sampled low, the register reads its reset value" -- not
    // "whenever rst_n is low". Writing it the second way would be a
    // property about an asynchronous reset this design does not have, and
    // would fail on correct RTL.
    // ===============================================================

    // ---- R1: architectural state is at its reset value --------------
    // The internal view. Every register with a reset clause in the RTL
    // appears here; the list was taken from the reset clauses, not from
    // memory, so a register added later without a property is visible as
    // a diff rather than as a silent gap.
    always @(posedge clk) begin
        if (f_past_valid && !$past(rst_n)) begin
            // baud generator
            assert(baud_cnt    == 8'd0);
            // TX engine
            assert(tx_state    == TX_IDLE);
            assert(tx_os       == 4'd0);
            assert(tx_bit      == 3'd0);
            assert(tx_shift    == 8'd0);
            assert(tx_par_bit  == 1'b0);
            assert(tx_line     == 1'b1);   // idle line is HIGH, not 0
            assert(tx_pop      == 1'b0);
            // RX engine
            assert(rx_sync     == 1'b1);   // idle line is HIGH, not 0
            assert(rx_state    == RX_IDLE);
            assert(rx_os       == 4'd0);
            assert(rx_bit      == 3'd0);
            assert(rx_shift    == 8'd0);
            assert(rx_par_rcvd == 1'b0);
            assert(rx_push     == 1'b0);
            assert(rx_push_data== 8'd0);
            assert(frame_err   == 1'b0);
            assert(parity_err  == 1'b0);
            assert(overrun_err == 1'b0);
            // FIFO pointers and counts
            assert(tx_wptr     == 3'd0);
            assert(tx_rptr     == 3'd0);
            assert(tx_cnt      == 4'd0);
            assert(rx_wptr     == 3'd0);
            assert(rx_rptr     == 3'd0);
            assert(rx_cnt      == 4'd0);
            // Programmable registers
            assert(ctrl        == 5'd0);
            assert(baud_div    == 8'd0);
            assert(int_en      == 3'd0);
        end
    end

    // ---- R2: the OBSERVABLE reset values, through the read port -----
    // R1 is about registers; R2 is about what software sees, which is
    // the obligation a CSR spec actually states. They are not the same
    // property: prdata is a combinational mux over paddr, so a decode
    // fault can leave every register correctly reset and still return
    // the wrong value.
    //
    // STATUS is the interesting one. Its reset value is NOT 0x00:
    //   {1'b0, overrun, parity, frame, rx_avail, rx_full, tx_empty, tx_full}
    //   = {0,0,0,0, 0,0, 1, 0} = 8'h02
    // because tx_empty is a live decode of tx_cnt == 0, which reset makes
    // true. A reader who assumed "registers reset to zero" would write
    // 8'h00 here and the property would be wrong while the design was
    // right -- the third of the three vacuity/self-fulfilment shapes
    // listed in the 2026-09-21 notes, caught by deriving the constant
    // from the RTL's own concatenation rather than by assuming it.
    always @(posedge clk) begin
        if (f_past_valid && !$past(rst_n)) begin
            if (paddr == ADDR_CTRL)     assert(prdata == 8'h00);
            if (paddr == ADDR_STATUS)   assert(prdata == 8'h02);
            if (paddr == ADDR_BAUD_DIV) assert(prdata == 8'h00);
            if (paddr == ADDR_INT_EN)   assert(prdata == 8'h00);
            if (paddr == ADDR_TX_DATA)  assert(prdata == 8'h00);
            // ADDR_RX_DATA is DELIBERATELY ABSENT. It reads rx_fifo[rx_rptr],
            // and the FIFO array has no reset clause: its contents after
            // reset are whatever they were, which is a real and intentional
            // property of the design (resetting 8 bytes of storage costs
            // area for no benefit when rx_cnt == 0 makes them unreadable
            // through the intended protocol). Asserting a value here would
            // be asserting something false. Mutant M7 exists to prove this
            // omission is deliberate and not an oversight -- it corrupts the
            // FIFO contents at reset and is REQUIRED TO SURVIVE.
        end
    end

    // ---- R3: no interrupt out of reset ------------------------------
    // Cheap, and the one reset property with an external consequence: a
    // core that asserts irq before software has enabled anything will
    // take a spurious interrupt on every boot. irq is combinational over
    // int_en and the live flags, so this is implied by R1 -- but it is
    // the implication a reviewer wants stated, and it is what M6 breaks.
    always @(posedge clk)
        if (f_past_valid && !$past(rst_n))
            assert(irq == 1'b0);

    // ---- R4: reset DOMINATES a concurrent bus write -----------------
    // The register-write block is
    //     if (!rst_n) ... else if (wr_en) ...
    // so reset wins. That priority is a choice, it is invisible in a
    // waveform unless a write happens to land in the reset window, and
    // inverting it is a one-line edit -- which is exactly the class of
    // defect formal is better at than simulation, because the solver will
    // construct the coincidence that a directed test never happens to hit.
    //
    // Stated as: it does not matter what the bus was doing in the reset
    // cycle. R1 already covers the values; what R4 adds is that it holds
    // under an ACTIVE write, which the solver must now actually exhibit.
    //
    // MEASURED REDUNDANCY (2026-09-22, stage 5 of run_reset_formal.sh).
    // R4 detects nothing R1 does not. The suite was run with R4 removed and
    // with ONLY R4 kept, against M3 (the very defect R4 was written for):
    // BOTH variants detect it. R1 asserts the reset values unconditionally,
    // so the concurrent-write case was already inside it.
    //
    // R4 is kept and annotated rather than deleted, for two reasons. It
    // states an INTENT -- that reset has priority over the bus -- which R1
    // only implies, and a reader of the property list should be able to see
    // that the priority was considered. And it would earn its detection
    // power the moment R1 were narrowed to a quiet bus, which is how a
    // larger design would have to write R1.
    //
    // This is a FOURTH way a property can be worth less than it looks, to
    // add to the three listed in notes/2026-09-21-*.md. It is not vacuity:
    // R4's antecedent is satisfiable (cover C_R2, reached at step 4) and it
    // is a true statement about real behaviour. It is SUBSUMPTION, and the
    // three vacuity tests all pass on it. Only a deletion experiment finds
    // it.
    always @(posedge clk) begin
        if (f_past_valid && !$past(rst_n) && $past(wr_en)) begin
            assert(ctrl     == 5'd0);
            assert(baud_div == 8'd0);
            assert(int_en   == 3'd0);
            assert(tx_cnt   == 4'd0);
        end
    end

    // ---- COVERS: R1-R4 are not vacuous ------------------------------
    // 2026-09-21's lesson, applied in advance rather than after the fact.
    // R1-R4 are implications, and an implication whose antecedent is
    // never satisfied passes for free. Worse, the antecedent here
    // (!$past(rst_n)) IS satisfiable trivially at step 1, because the
    // environment assumption forces reset at step 0 -- so the naive cover
    // proves nothing at all.
    //
    // Both covers below therefore demand a reset that RETURNS, after the
    // design has left its reset state. The runner additionally requires
    // every cover to be reached at step >= 2, the standing guard added
    // 2026-09-21.
    always @(posedge clk) begin
        if (f_past_valid && $past(f_past_valid) && !$past(rst_n)) begin
            // C_R1: reset re-applied after the design was running, with
            // something non-trivial in flight. If this is unreachable,
            // R1 has only ever been evaluated on the power-on edge.
            cover($past(rst_n, 2) && $past(wr_en, 2));
        end
    end

    always @(posedge clk) begin
        if (f_past_valid && $past(f_past_valid) && !$past(rst_n) && $past(wr_en))
            // C_R2: R4's antecedent specifically -- a write in the reset
            // cycle. R4 is the only property here that can be vacuous in a
            // way R1 does not already cover.
            cover(1'b1);
    end
`endif // FORMAL_CSR_RESET

endmodule
