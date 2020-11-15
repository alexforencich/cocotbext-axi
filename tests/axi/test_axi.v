/*

Copyright (c) 2020 Alex Forencich

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

*/

// Language: Verilog 2001

`timescale 1ns / 1ns

/*
 * AXI4 test module
 */
module test_axi #
(
    parameter DATA_WIDTH = 32,
    parameter ADDR_WIDTH = 32,
    parameter STRB_WIDTH = (DATA_WIDTH/8),
    parameter ID_WIDTH = 8,
    parameter AWUSER_WIDTH = 1,
    parameter WUSER_WIDTH = 1,
    parameter BUSER_WIDTH = 1,
    parameter ARUSER_WIDTH = 1,
    parameter RUSER_WIDTH = 1
)
(
    input  wire                     clk,
    input  wire                     rst,

    inout  wire [ID_WIDTH-1:0]      axi_awid,
    inout  wire [ADDR_WIDTH-1:0]    axi_awaddr,
    inout  wire [7:0]               axi_awlen,
    inout  wire [2:0]               axi_awsize,
    inout  wire [1:0]               axi_awburst,
    inout  wire                     axi_awlock,
    inout  wire [3:0]               axi_awcache,
    inout  wire [2:0]               axi_awprot,
    inout  wire [3:0]               axi_awqos,
    inout  wire [3:0]               axi_awregion,
    inout  wire [AWUSER_WIDTH-1:0]  axi_awuser,
    inout  wire                     axi_awvalid,
    inout  wire                     axi_awready,
    inout  wire [DATA_WIDTH-1:0]    axi_wdata,
    inout  wire [STRB_WIDTH-1:0]    axi_wstrb,
    inout  wire                     axi_wlast,
    inout  wire [WUSER_WIDTH-1:0]   axi_wuser,
    inout  wire                     axi_wvalid,
    inout  wire                     axi_wready,
    inout  wire [ID_WIDTH-1:0]      axi_bid,
    inout  wire [1:0]               axi_bresp,
    inout  wire [BUSER_WIDTH-1:0]   axi_buser,
    inout  wire                     axi_bvalid,
    inout  wire                     axi_bready,
    inout  wire [ID_WIDTH-1:0]      axi_arid,
    inout  wire [ADDR_WIDTH-1:0]    axi_araddr,
    inout  wire [7:0]               axi_arlen,
    inout  wire [2:0]               axi_arsize,
    inout  wire [1:0]               axi_arburst,
    inout  wire                     axi_arlock,
    inout  wire [3:0]               axi_arcache,
    inout  wire [2:0]               axi_arprot,
    inout  wire [3:0]               axi_arqos,
    inout  wire [3:0]               axi_arregion,
    inout  wire [ARUSER_WIDTH-1:0]  axi_aruser,
    inout  wire                     axi_arvalid,
    inout  wire                     axi_arready,
    inout  wire [ID_WIDTH-1:0]      axi_rid,
    inout  wire [DATA_WIDTH-1:0]    axi_rdata,
    inout  wire [1:0]               axi_rresp,
    inout  wire                     axi_rlast,
    inout  wire [RUSER_WIDTH-1:0]   axi_ruser,
    inout  wire                     axi_rvalid,
    inout  wire                     axi_rready
);

endmodule
