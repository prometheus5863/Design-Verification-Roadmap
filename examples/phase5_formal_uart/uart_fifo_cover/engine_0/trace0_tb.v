`ifndef VERILATOR
module testbench;
  reg [4095:0] vcdfile;
  reg clock;
`else
module testbench(input clock, output reg genclock);
  initial genclock = 1;
`endif
  reg genclock = 1;
  reg [31:0] cycle = 0;
  reg [3:0] PI_paddr;
  reg [0:0] PI_psel;
  reg [7:0] PI_pwdata;
  reg [0:0] PI_rx;
  reg [0:0] PI_pwrite;
  reg [0:0] PI_penable;
  reg [0:0] PI_rst_n;
  wire [0:0] PI_clk = clock;
  uart_controller UUT (
    .paddr(PI_paddr),
    .psel(PI_psel),
    .pwdata(PI_pwdata),
    .rx(PI_rx),
    .pwrite(PI_pwrite),
    .penable(PI_penable),
    .rst_n(PI_rst_n),
    .clk(PI_clk)
  );
`ifndef VERILATOR
  initial begin
    if ($value$plusargs("vcd=%s", vcdfile)) begin
      $dumpfile(vcdfile);
      $dumpvars(0, testbench);
    end
    #5 clock = 0;
    while (genclock) begin
      #5 clock = 0;
      #5 clock = 1;
    end
  end
`endif
  initial begin
`ifndef VERILATOR
    #1;
`endif
    // UUT.$auto$async2sync.\cc:107:execute$924  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$922  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$928  = 1'b1;
    UUT.baud_cnt = 8'b00000000;
    UUT.baud_div = 8'b00000000;
    UUT.ctrl = 5'b00011;
    UUT.f_past_valid = 1'b0;
    UUT.frame_err = 1'b0;
    UUT.int_en = 3'b000;
    UUT.overrun_err = 1'b0;
    UUT.parity_err = 1'b0;
    UUT.rx_bit = 3'b000;
    UUT.rx_cnt = 4'b0000;
    UUT.rx_os = 4'b0000;
    UUT.rx_par_rcvd = 1'b0;
    UUT.rx_push = 1'b0;
    UUT.rx_push_data = 8'b00000000;
    UUT.rx_rptr = 3'b000;
    UUT.rx_shift = 8'b00000000;
    UUT.rx_state = 3'b000;
    UUT.rx_sync = 1'b1;
    UUT.rx_wptr = 3'b000;
    UUT.tx_bit = 3'b000;
    UUT.tx_cnt = 4'b0000;
    UUT.tx_line = 1'b1;
    UUT.tx_os = 4'b0000;
    UUT.tx_par_bit = 1'b0;
    UUT.tx_pop = 1'b0;
    UUT.tx_rptr = 3'b000;
    UUT.tx_shift = 8'b00000000;
    UUT.tx_state = 3'b000;
    UUT.tx_wptr = 3'b001;
    UUT.rx_fifo[3'b000] = 8'b00000000;
    UUT.tx_fifo[3'b000] = 8'b00000010;
    UUT.tx_fifo[3'b001] = 8'b00000000;

    // state 0
    PI_paddr = 4'b0000;
    PI_psel = 1'b1;
    PI_pwdata = 8'b00000011;
    PI_rx = 1'b1;
    PI_pwrite = 1'b1;
    PI_penable = 1'b1;
    PI_rst_n = 1'b0;
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
      PI_paddr <= 4'b0000;
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000001;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    // state 2
    if (cycle == 1) begin
      PI_paddr <= 4'b0011;
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000000;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    // state 3
    if (cycle == 2) begin
      PI_paddr <= 4'b0000;
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000011;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    // state 4
    if (cycle == 3) begin
      PI_paddr <= 4'b0000;
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000011;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b0;
      PI_penable <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    // state 5
    if (cycle == 4) begin
      PI_paddr <= 4'b0010;
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000000;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b0;
      PI_penable <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    // state 6
    if (cycle == 5) begin
      PI_paddr <= 4'b0000;
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000011;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_rst_n <= 1'b1;
    end

    genclock <= cycle < 6;
    cycle <= cycle + 1;
  end
endmodule
