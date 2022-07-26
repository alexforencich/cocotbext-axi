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
AxiLiteAWBus, AxiLiteAWTransaction, AxiLiteAWSource, AxiLiteAWSink, AxiLiteAWMonitor = define_stream("AxiLiteAW",
    signals=["awaddr", "awvalid", "awready"],
    optional_signals=["awprot"],
    signal_widths={"awprot": 3}
)

# Write data channel
AxiLiteWBus, AxiLiteWTransaction, AxiLiteWSource, AxiLiteWSink, AxiLiteWMonitor = define_stream("AxiLiteW",
    signals=["wdata", "wvalid", "wready"],
    optional_signals=["wstrb"]
)

# Write response channel
AxiLiteBBus, AxiLiteBTransaction, AxiLiteBSource, AxiLiteBSink, AxiLiteBMonitor = define_stream("AxiLiteB",
    signals=["bvalid", "bready"],
    optional_signals=["bresp"],
    signal_widths={"bresp": 2}
)

# Read address channel
AxiLiteARBus, AxiLiteARTransaction, AxiLiteARSource, AxiLiteARSink, AxiLiteARMonitor = define_stream("AxiLiteAR",
    signals=["araddr", "arvalid", "arready"],
    optional_signals=["arprot"],
    signal_widths={"arprot": 3}
)

# Read data channel
AxiLiteRBus, AxiLiteRTransaction, AxiLiteRSource, AxiLiteRSink, AxiLiteRMonitor = define_stream("AxiLiteR",
    signals=["rdata", "rvalid", "rready"],
    optional_signals=["rresp"],
    signal_widths={"rresp": 2}
)


class AxiLiteWriteBus:
    def __init__(self, aw=None, w=None, b=None):
        self.aw = aw
        self.w = w
        self.b = b

    @classmethod
    def from_entity(cls, entity, **kwargs):
        aw = AxiLiteAWBus.from_entity(entity, **kwargs)
        w = AxiLiteWBus.from_entity(entity, **kwargs)
        b = AxiLiteBBus.from_entity(entity, **kwargs)
        return cls(aw, w, b)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        aw = AxiLiteAWBus.from_prefix(entity, prefix, **kwargs)
        w = AxiLiteWBus.from_prefix(entity, prefix, **kwargs)
        b = AxiLiteBBus.from_prefix(entity, prefix, **kwargs)
        return cls(aw, w, b)

    @classmethod
    def from_channels(cls, aw, w, b):
        return cls(aw, w, b)


class AxiLiteReadBus:
    def __init__(self, ar=None, r=None):
        self.ar = ar
        self.r = r

    @classmethod
    def from_entity(cls, entity, **kwargs):
        ar = AxiLiteARBus.from_entity(entity, **kwargs)
        r = AxiLiteRBus.from_entity(entity, **kwargs)
        return cls(ar, r)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        ar = AxiLiteARBus.from_prefix(entity, prefix, **kwargs)
        r = AxiLiteRBus.from_prefix(entity, prefix, **kwargs)
        return cls(ar, r)

    @classmethod
    def from_channels(cls, ar, r):
        return cls(ar, r)


class AxiLiteBus:
    def __init__(self, write=None, read=None, **kwargs):
        self.write = write
        self.read = read

    @classmethod
    def from_entity(cls, entity, **kwargs):
        write = AxiLiteWriteBus.from_entity(entity, **kwargs)
        read = AxiLiteReadBus.from_entity(entity, **kwargs)
        return cls(write, read)

    @classmethod
    def from_prefix(cls, entity, prefix, **kwargs):
        write = AxiLiteWriteBus.from_prefix(entity, prefix, **kwargs)
        read = AxiLiteReadBus.from_prefix(entity, prefix, **kwargs)
        return cls(write, read)

    @classmethod
    def from_channels(cls, aw, w, b, ar, r):
        write = AxiLiteWriteBus.from_channels(aw, w, b)
        read = AxiLiteReadBus.from_channels(ar, r)
        return cls(write, read)
