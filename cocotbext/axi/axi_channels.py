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
AxiAWTransaction, AxiAWSource, AxiAWSink, AxiAWMonitor = define_stream("AxiAW",
    signals=["awid", "awaddr", "awlen", "awsize", "awburst", "awprot", "awvalid", "awready"],
    optional_signals=["awlock", "awcache", "awqos", "awregion", "awuser"],
    signal_widths={"awlen": 8, "awsize": 3, "awburst": 2, "awlock": 1,
        "awcache": 4, "awprot": 3, "awqos": 4, "awregion": 4}
)

# Write data channel
AxiWTransaction, AxiWSource, AxiWSink, AxiWMonitor = define_stream("AxiW",
    signals=["wdata", "wstrb", "wlast", "wvalid", "wready"],
    optional_signals=["wuser"],
    signal_widths={"wlast": 1}
)

# Write response channel
AxiBTransaction, AxiBSource, AxiBSink, AxiBMonitor = define_stream("AxiB",
    signals=["bid", "bresp", "bvalid", "bready"],
    optional_signals=["buser"],
    signal_widths={"bresp": 2}
)

# Read address channel
AxiARTransaction, AxiARSource, AxiARSink, AxiARMonitor = define_stream("AxiAR",
    signals=["arid", "araddr", "arlen", "arsize", "arburst", "arprot", "arvalid", "arready"],
    optional_signals=["arlock", "arcache", "arqos", "arregion", "aruser"],
    signal_widths={"arlen": 8, "arsize": 3, "arburst": 2, "arlock": 1,
        "arcache": 4, "arprot": 3, "arqos": 4, "arregion": 4}
)

# Read data channel
AxiRTransaction, AxiRSource, AxiRSink, AxiRMonitor = define_stream("AxiR",
    signals=["rid", "rdata", "rresp", "rlast", "rvalid", "rready"],
    optional_signals=["ruser"],
    signal_widths={"rresp": 2, "rlast": 1}
)
