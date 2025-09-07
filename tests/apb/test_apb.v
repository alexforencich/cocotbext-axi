/*

Copyright (c) 2025 Alex Forencich

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
 * APB test module
 */
module test_apb #
(
    parameter DATA_W = 32,
    parameter ADDR_W = 16,
    parameter STRB_W = (DATA_W/8)
)
(
    input  wire               clk,
    input  wire               rst,

    inout  wire [ADDR_W-1:0]  apb_paddr,
    inout  wire [2:0]         apb_pprot,
    inout  wire               apb_psel,
    inout  wire               apb_penable,
    inout  wire               apb_pwrite,
    inout  wire [DATA_W-1:0]  apb_pwdata,
    inout  wire [STRB_W-1:0]  apb_pstrb,
    inout  wire               apb_pready,
    inout  wire [DATA_W-1:0]  apb_prdata,
    inout  wire               apb_pslverr
);

endmodule
