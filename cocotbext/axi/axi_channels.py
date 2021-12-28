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
AxiAWBus, AxiAWTransaction, AxiAWSource, AxiAWSink, AxiAWMonitor = define_stream("AxiAW",
    signals=["awid", "awaddr", "awlen", "awsize", "awburst", "awvalid", "awready"],
    optional_signals=["awlock", "awcache", "awprot", "awqos", "awregion", "awuser"],
    signal_widths={"awlen": 8, "awsize": 3, "awburst": 2, "awlock": 1,
        "awcache": 4, "awprot": 3, "awqos": 4, "awregion": 4}
)

# Write data channel
AxiWBus, AxiWTransaction, AxiWSource, AxiWSink, AxiWMonitor = define_stream("AxiW",
    signals=["wdata", "wlast", "wvalid", "wready"],
    optional_signals=["wstrb", "wuser"],
    signal_widths={"wlast": 1}
)

# Write response channel
AxiBBus, AxiBTransaction, AxiBSource, AxiBSink, AxiBMonitor = define_stream("AxiB",
    signals=["bid", "bvalid", "bready"],
    optional_signals=["bresp", "buser"],
    signal_widths={"bresp": 2}
)

# Read address channel
AxiARBus, AxiARTransaction, AxiARSource, AxiARSink, AxiARMonitor = define_stream("AxiAR",
    signals=["arid", "araddr", "arlen", "arsize", "arburst", "arvalid", "arready"],
    optional_signals=["arlock", "arcache", "arprot", "arqos", "arregion", "aruser"],
    signal_widths={"arlen": 8, "arsize": 3, "arburst": 2, "arlock": 1,
        "arcache": 4, "arprot": 3, "arqos": 4, "arregion": 4}
)

# Read data channel
AxiRBus, AxiRTransaction, AxiRSource, AxiRSink, AxiRMonitor = define_stream("AxiR",
    signals=["rid", "rdata", "rlast", "rvalid", "rready"],
    optional_signals=["rresp", "ruser"],
    signal_widths={"rresp": 2, "rlast": 1}
)


class AxiWriteBus:
    def __init__(self, aw=None, w=None, b=None):
        self.aw = aw
        self.w = w
        self.b = b

    @classmethod
    def from_entity(cls, entity, **kwargs):
        aw = AxiAWBus.from_entity(entity, **kwargs)
        w = AxiWBus.from_entity(entity, **kwargs)
        b = AxiBBus.from_entity(entity, **kwargs)
        return cls(aw, w, b)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        aw = AxiAWBus.from_prefix(entity, prefix, **kwargs)
        w = AxiWBus.from_prefix(entity, prefix, **kwargs)
        b = AxiBBus.from_prefix(entity, prefix, **kwargs)
        return cls(aw, w, b)

    @classmethod
    def from_channels(cls, aw, w, b):
        return cls(aw, w, b)


class AxiReadBus:
    def __init__(self, ar=None, r=None):
        self.ar = ar
        self.r = r

    @classmethod
    def from_entity(cls, entity, **kwargs):
        ar = AxiARBus.from_entity(entity, **kwargs)
        r = AxiRBus.from_entity(entity, **kwargs)
        return cls(ar, r)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        ar = AxiARBus.from_prefix(entity, prefix, **kwargs)
        r = AxiRBus.from_prefix(entity, prefix, **kwargs)
        return cls(ar, r)

    @classmethod
    def from_channels(cls, ar, r):
        return cls(ar, r)


class AxiBus:
    def __init__(self, write=None, read=None, **kwargs):
        self.write = write
        self.read = read

    @classmethod
    def from_entity(cls, entity, **kwargs):
        write = AxiWriteBus.from_entity(entity, **kwargs)
        read = AxiReadBus.from_entity(entity, **kwargs)
        return cls(write, read)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        write = AxiWriteBus.from_prefix(entity, prefix, **kwargs)
        read = AxiReadBus.from_prefix(entity, prefix, **kwargs)
        return cls(write, read)

    @classmethod
    def from_channels(cls, aw, w, b, ar, r):
        write = AxiWriteBus.from_channels(aw, w, b)
        read = AxiReadBus.from_channels(ar, r)
        return cls(write, read)
