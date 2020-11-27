"""

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

"""

from .stream import define_stream

# Write address channel
AxiLiteAWTransaction, AxiLiteAWSource, AxiLiteAWSink, AxiLiteAWMonitor = define_stream("AxiLiteAW",
    signals=["awaddr", "awprot", "awvalid", "awready"],
    signal_widths={"awprot": 3}
)

# Write data channel
AxiLiteWTransaction, AxiLiteWSource, AxiLiteWSink, AxiLiteWMonitor = define_stream("AxiLiteW",
    signals=["wdata", "wstrb", "wvalid", "wready"]
)

# Write response channel
AxiLiteBTransaction, AxiLiteBSource, AxiLiteBSink, AxiLiteBMonitor = define_stream("AxiLiteB",
    signals=["bresp", "bvalid", "bready"],
    signal_widths={"bresp": 2}
)

# Read address channel
AxiLiteARTransaction, AxiLiteARSource, AxiLiteARSink, AxiLiteARMonitor = define_stream("AxiLiteAR",
    signals=["araddr", "arprot", "arvalid", "arready"],
    signal_widths={"arprot": 3}
)

# Read data channel
AxiLiteRTransaction, AxiLiteRSource, AxiLiteRSink, AxiLiteRMonitor = define_stream("AxiLiteR",
    signals=["rdata", "rresp", "rvalid", "rready"],
    signal_widths={"rresp": 2}
)
