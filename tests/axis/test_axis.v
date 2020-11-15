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
 * AXI4-Stream test
 */
module test_axis #
(
    parameter DATA_WIDTH = 8,
    parameter KEEP_WIDTH = (DATA_WIDTH/8),
    parameter ID_WIDTH = 8,
    parameter DEST_WIDTH = 8,
    parameter USER_WIDTH = 1
)
(
    input  wire                   clk,
    input  wire                   rst,

    inout  wire [DATA_WIDTH-1:0]  axis_tdata,
    inout  wire [KEEP_WIDTH-1:0]  axis_tkeep,
    inout  wire                   axis_tvalid,
    inout  wire                   axis_tready,
    inout  wire                   axis_tlast,
    inout  wire [ID_WIDTH-1:0]    axis_tid,
    inout  wire [DEST_WIDTH-1:0]  axis_tdest,
    inout  wire [USER_WIDTH-1:0]  axis_tuser
);

endmodule
