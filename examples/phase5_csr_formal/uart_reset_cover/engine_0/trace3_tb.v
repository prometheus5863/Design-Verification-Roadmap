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
  wire [0:0] PI_clk = clock;
  reg [0:0] PI_psel;
  reg [7:0] PI_pwdata;
  reg [0:0] PI_rst_n;
  reg [0:0] PI_rx;
  reg [0:0] PI_pwrite;
  reg [0:0] PI_penable;
  reg [3:0] PI_paddr;
  uart_controller UUT (
    .clk(PI_clk),
    .psel(PI_psel),
    .pwdata(PI_pwdata),
    .rst_n(PI_rst_n),
    .rx(PI_rx),
    .pwrite(PI_pwrite),
    .penable(PI_penable),
    .paddr(PI_paddr)
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
    // UUT.$auto$async2sync.\cc:107:execute$1382  = 1'b0;
    // UUT.$auto$async2sync.\cc:107:execute$1394  = 1'b0;
    // UUT.$auto$async2sync.\cc:107:execute$1400  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$1386  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$1392  = 1'b1;
    // UUT.$auto$async2sync.\cc:116:execute$1398  = 1'b1;
    UUT._witness_.anyinit_procdff_1031 = 1'b1;
    UUT._witness_.anyinit_procdff_1032 = 1'b1;
    UUT._witness_.anyinit_procdff_1033 = 1'b1;
    UUT._witness_.anyinit_procdff_1034 = 1'b1;
    UUT._witness_.anyinit_procdff_1035 = 1'b1;
    UUT._witness_.anyinit_procdff_1036 = 1'b0;
    UUT._witness_.anyinit_procdff_1037 = 1'b0;
    UUT._witness_.anyinit_procdff_1038 = 1'b0;
    UUT._witness_.anyinit_procdff_1039 = 1'b0;
    UUT.baud_cnt = 8'b00000000;
    UUT.baud_div = 8'b00000000;
    UUT.ctrl = 5'b00000;
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
    UUT.rx_sync = 1'b0;
    UUT.rx_wptr = 3'b000;
    UUT.tx_bit = 3'b000;
    UUT.tx_cnt = 4'b1000;
    UUT.tx_line = 1'b1;
    UUT.tx_os = 4'b0000;
    UUT.tx_par_bit = 1'b0;
    UUT.tx_pop = 1'b0;
    UUT.tx_rptr = 3'b001;
    UUT.tx_shift = 8'b00000000;
    UUT.tx_state = 3'b000;
    UUT.tx_wptr = 3'b000;
    UUT.rx_fifo[3'b000] = 8'b00001100;
    UUT.tx_fifo[3'b001] = 8'b10110000;
    UUT.tx_fifo[3'b000] = 8'b00000000;

    // state 0
    PI_psel = 1'b0;
    PI_pwdata = 8'b10110010;
    PI_rst_n = 1'b0;
    PI_rx = 1'b0;
    PI_pwrite = 1'b1;
    PI_penable = 1'b1;
    PI_paddr = 4'b0011;
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00010110;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 2
    if (cycle == 1) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b10110010;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 3
    if (cycle == 2) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b10110010;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 4
    if (cycle == 3) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000000;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 5
    if (cycle == 4) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000010;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 6
    if (cycle == 5) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b11000100;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 7
    if (cycle == 6) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000000;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 8
    if (cycle == 7) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00000010;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b1;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    // state 9
    if (cycle == 8) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b00100000;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b0;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0001;
    end

    // state 10
    if (cycle == 9) begin
      PI_psel <= 1'b1;
      PI_pwdata <= 8'b10110010;
      PI_rst_n <= 1'b1;
      PI_rx <= 1'b0;
      PI_pwrite <= 1'b1;
      PI_penable <= 1'b1;
      PI_paddr <= 4'b0011;
    end

    genclock <= cycle < 10;
    cycle <= cycle + 1;
  end
endmodule
