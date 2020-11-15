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
 * AXI lite test module
 */
module test_axil #
(
    parameter DATA_WIDTH = 32,
    parameter ADDR_WIDTH = 16,
    parameter STRB_WIDTH = (DATA_WIDTH/8)
)
(
    input  wire                   clk,
    input  wire                   rst,

    inout  wire [ADDR_WIDTH-1:0]  axil_awaddr,
    inout  wire [2:0]             axil_awprot,
    inout  wire                   axil_awvalid,
    inout  wire                   axil_awready,
    inout  wire [DATA_WIDTH-1:0]  axil_wdata,
    inout  wire [STRB_WIDTH-1:0]  axil_wstrb,
    inout  wire                   axil_wvalid,
    inout  wire                   axil_wready,
    inout  wire [1:0]             axil_bresp,
    inout  wire                   axil_bvalid,
    inout  wire                   axil_bready,
    inout  wire [ADDR_WIDTH-1:0]  axil_araddr,
    inout  wire [2:0]             axil_arprot,
    inout  wire                   axil_arvalid,
    inout  wire                   axil_arready,
    inout  wire [DATA_WIDTH-1:0]  axil_rdata,
    inout  wire [1:0]             axil_rresp,
    inout  wire                   axil_rvalid,
    inout  wire                   axil_rready
);

endmodule
