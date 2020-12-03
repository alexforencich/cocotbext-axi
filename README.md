# AXI interface modules for Cocotb

GitHub repository: https://github.com/alexforencich/cocotbext-axi

## Introduction

AXI, AXI lite, and AXI stream simulation models for cocotb.

## Installation

Installation from pip (release version, stable):

    $ pip install cocotbext-axi

Installation from git (latest development version, potentially unstable):

    $ pip install https://github.com/alexforencich/cocotbext-axi/archive/master.zip

Installation for active development:

    $ git clone https://github.com/alexforencich/cocotbext-axi
    $ pip install -e cocotbext-axi

## Documentation and usage examples

See the `tests` directory, [verilog-axi](https://github.com/alexforencich/verilog-axi), and [verilog-axis](https://github.com/alexforencich/verilog-axis) for complete testbenches using these modules.

### AXI and AXI lite master

The `AxiMaster` and `AxiLiteMaster` classes implement AXI masters and are capable of generating read and write operations against AXI slaves.  Requested operations will be split and aligned according to the AXI specification.  The `AxiMaster` module is capable of generating narrow bursts, handling multiple in-flight operations, and handling reordering and interleaving in responses across different transaction IDs.

The `AxiMaster` is a wrapper around `AxiMasterWrite` and `AxiMasterRead`.  Similarly, `AxiLiteMaster` is a wrapper around `AxiLiteMasterWrite` and `AxiLiteMasterRead`.  If a read-only or write-only interface is required instead of a full interface, use the corresponding read-only or write-only variant, the usage and API are exactly the same.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import AxiMaster

    axi_master = AxiMaster(dut, "s_axi", dut.clk, dut.rst)

The modules use `cocotb.bus.Bus` internally to automatically connect to the corresponding signals in the bus, presuming they are named according to the AXI spec and have a common prefix.

Once the module is instantiated, read and write operations can be initiated in a few different ways.

First, non-blocking operations can be started with `init_read()` and `init_write()`.  These methods will queue up a read or write operation to be carried out over the interface.  The result of the operation can be retrieved with `get_read_data()` and `get_write_resp()`.  To monitor the status of the module, `idle()`, `wait()`, `wait_read()`, and `wait_write()` can be used.  For example:

    axi_master.init_write(0x0000, b'test')
    await axi_master.wait()
    resp = axi_master.get_write_resp()
    axi_master.init_read(0x0000, 4)
    await axi_master.wait()
    data = axi_master.get_read_data()

Alternatively, an event object can be provided as an argument to `init_read()` and `init_write()`, and the result can be retrieved from `Event.data`.  For example:

    event = Event()
    axi_master.init_write(0x0000, b'test', event=event)
    await event.wait()
    resp = event.data
    event = Event()
    axi_master.init_read(0x0000, 4, event=event)
    await event.wait()
    resp = event.data

Second, blocking operations can be carried out with `read()` and `write()` and their associated word-access wrappers.  Multiple concurrent operations started from different coroutines are handled correctly.  For example:

    await axi_master.write(0x0000, b'test')
    data = await axi_master.read(0x0000, 4)

`read()`, `write()`, `get_read_data()`, and `get_write_resp()` return `namedtuple` objects containing _address_, _data_ or _length_, and _resp_.

#### `AxiMaster` and `AxiLiteMaster` constructor parameters

* _entity_: object that contains the AXI slave interface signals
* _name_: signal name prefix (e.g. for `s_axi_awaddr`, the prefix is `s_axi`)
* _clock_: clock signal
* _reset_: reset signal (optional)

#### Additional parameters for `AxiMaster`

* _max_burst_len_: maximum burst length in cycles, range 1-256, default 256.

#### Methods

* `init_read(address, length, ...)`: initiate reading _length_ bytes, starting at _address_
* `init_write(address, data, ...)`: initiate writing _data_ (bytes), starting from _address_
* `idle()`: returns _True_ when there are no outstanding operations in progress
* `wait()`: blocking wait until all outstanding operations complete
* `wait_read()`: wait until all outstanding read operations complete
* `wait_write()`: wait until all outstanding write operations complete
* `read_data_ready()`: determine if any read read data is available
* `get_read_data()`: fetch first available read data
* `write_resp_ready()`: determine if any write response is available
* `get_write_resp()`: fetch first available write response
* `read(address, length, ...)`: read _length_ bytes, starting at _address_
* `read_words(address, count, byteorder, ws, ...)`: read _count_ _ws_-byte words, starting at _address_, default word size of `2`, default _byteorder_ `"little"`
* `read_dwords(address, count, byteorder, ...)`: read _count_ 4-byte dwords, starting at _address_, default _byteorder_ `"little"`
* `read_qwords(address, count, byteorder, ...)`: read _count_ 8-byte qwords, starting at _address_, default _byteorder_ `"little"`
* `read_byte(address, ...)`: read single byte at _address_
* `read_word(address, byteorder, ws, ...)`: read single _ws_-byte word at _address_, default word size of `2`, default _byteorder_ `"little"`
* `read_dword(address, byteorder, ...)`: read single 4-byte dword at _address_, default _byteorder_ `"little"`
* `read_qword(address, byteorder, ...)`: read single 8-byte qword at _address_, default _byteorder_ `"little"`
* `write(address, data, ...)`: write _data_ (bytes), starting at _address_
* `write_words(address, data, byteorder, ws, ...)`: write _data_ (_ws_-byte words), starting at _address_, default word size of `2`, default _byteorder_ `"little"`
* `write_dwords(address, data, byteorder, ...)`: write _data_ (4-byte dwords), starting at _address_, default _byteorder_ `"little"`
* `write_qwords(address, data, byteorder, ...)`: write _data_ (8-byte qwords), starting at _address_, default _byteorder_ `"little"`
* `write_byte(address, data, ...)`: write single byte at _address_
* `write_word(address, data, byteorder, ws, ...)`: write single _ws_-byte word at _address_, default word size of `2`, default _byteorder_ `"little"`
* `write_dword(address, data, byteorder, ...)`: write single 4-byte dword at _address_, default _byteorder_ `"little"`
* `write_qword(address, data, byteorder, ...)`: write single 8-byte qword at _address_, default _byteorder_ `"little"`

#### Additional optional arguments for `AxiMaster`

* _arid_,_awid_: AXI ID for bursts, default automatically assigned
* _burst_: AXI burst type, default `AxiBurstType.INCR`
* _size_: AXI burst size, default maximum supported by interface
* _lock_: AXI lock type, default `AxiLockType.NORMAL`
* _cache_: AXI cache field, default `0b0011`
* _prot_: AXI protection flags, default `AxiProt.NONSECURE`
* _qos_: AXI QOS field, default `0`
* _region_: AXI region field, default `0`
* _user_: AXI user signal (awuser/aruser), default `0`
* _wuser_: AXI wuser signal, default `0` (write-related methods only)
* _event_: `Event` object used to wait on and retrieve result for specific operation, default `None` (`init_read()` and `init_write()` only).  If provided, the event will be triggered when the operation completes and the result returned via `Event.data` instead of `get_read_data()` or `get_write_resp()`.

#### Additional optional arguments for `AxiLiteMaster`

* _prot_: AXI protection flags, default `AxiProt.NONSECURE`
* _event_: `Event` object used to wait on and retrieve result for specific operation, default `None` (`init_read()` and `init_write()` only).  If provided, the event will be triggered when the operation completes and the result returned via `Event.data` instead of `get_read_data()` or `get_write_resp()`.

### AXI and AXI lite RAM

The `AxiRam` and `AxiLiteRam` classes implement AXI RAMs and are capable of completing read and write operations from upstream AXI masters.  The `AxiRam` module is capable of handling narrow bursts.

The `AxiRam` is a wrapper around `AxiRamWrite` and `AxiRamRead`.  Similarly, `AxiLiteRam` is a wrapper around `AxiLiteRamWrite` and `AxiLiteRamRead`.  If a read-only or write-only interface is required instead of a full interface, use the corresponding read-only or write-only variant, the usage and API are exactly the same.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import AxiRam

    axi_ram = AxiRam(dut, "m_axi", dut.clk, dut.rst, size=2**16)

The modules use `cocotb.bus.Bus` internally to automatically connect to the corresponding signals in the bus, presuming they are named according to the AXI spec and have a common prefix.

Once the module is instantiated, the memory contents can be accessed in a couple of different ways.  First, the `mmap` object can be accessed directly via the `mem` attribute.  Second, `read()`, `write()`, and various word-access wrappers are available.  Hex dump helper methods are also provided for debugging.  For example:

    axi_ram.write(0x0000, b'test')
    data = axi_ram.read(0x0000, 4)

Multi-port memories can be constructed by passing the `mem` object of the first instance to the other instances.  For example, here is how to create a four-port RAM:

    axi_ram_p1 = AxiRam(dut, "m00_axi", dut.clk, dut.rst, size=2**16)
    axi_ram_p2 = AxiRam(dut, "m01_axi", dut.clk, dut.rst, mem=axi_ram_p1.mem)
    axi_ram_p3 = AxiRam(dut, "m02_axi", dut.clk, dut.rst, mem=axi_ram_p1.mem)
    axi_ram_p4 = AxiRam(dut, "m03_axi", dut.clk, dut.rst, mem=axi_ram_p1.mem)

#### `AxiRam` and `AxiLiteRam` constructor parameters

* _entity_: object that contains the AXI master interface signals
* _name_: signal name prefix (e.g. for `m_axi_awaddr`, the prefix is `m_axi`)
* _clock_: clock signal
* _reset_: reset signal (optional)
* _size_: memory size in bytes (optional, default 1024)
* _mem_: mmap object to use (optional, overrides _size_)

#### Attributes:

* _mem_: directly access shared `mmap` object

#### Methods

* `read(address, length)`: read _length_ bytes, starting at _address_
* `read_words(address, count, byteorder, ws)`: read _count_ _ws_-byte words, starting at _address_, default word size of `2`, default _byteorder_ `"little"`
* `read_dwords(address, count, byteorder)`: read _count_ 4-byte dwords, starting at _address_, default _byteorder_ `"little"`
* `read_qwords(address, count, byteorder)`: read _count_ 8-byte qwords, starting at _address_, default _byteorder_ `"little"`
* `read_byte(address)`: read single byte at _address_
* `read_word(address, byteorder, ws)`: read single _ws_-byte word at _address_, default word size of `2`, default _byteorder_ `"little"`
* `read_dword(address, byteorder)`: read single 4-byte dword at _address_, default _byteorder_ `"little"`
* `read_qword(address, byteorder)`: read single 8-byte qword at _address_, default _byteorder_ `"little"`
* `write(address, data)`: write _data_ (bytes), starting at _address_
* `write_words(address, data, byteorder, ws)`: write _data_ (_ws_-byte words), starting at _address_, default word size of `2`, default _byteorder_ `"little"`
* `write_dwords(address, data, byteorder)`: write _data_ (4-byte dwords), starting at _address_, default _byteorder_ `"little"`
* `write_qwords(address, data, byteorder)`: write _data_ (8-byte qwords), starting at _address_, default _byteorder_ `"little"`
* `write_byte(address, data)`: write single byte at _address_
* `write_word(address, data, byteorder, ws)`: write single _ws_-byte word at _address_, default word size of `2`, default _byteorder_ `"little"`
* `write_dword(address, data, byteorder)`: write single 4-byte dword at _address_, default _byteorder_ `"little"`
* `write_qword(address, data, byteorder)`: write single 8-byte qword at _address_, default _byteorder_ `"little"`
* `hexdump(address, length, prefix)`: print hex dump of _length_ bytes starting from `address`, prefix lines with optional `prefix`
* `hexdump_line(address, length, prefix)`: return hex dump (list of str) of _length_ bytes starting from `address`, prefix lines with optional `prefix`
* `hexdump_str(address, length, prefix)`: return hex dump (str) of _length_ bytes starting from `address`, prefix lines with optional `prefix`

### AXI stream

The `AxiStreamSource`, `AxiStreamSink`, and `AxiStreamMonitor` classes can be used to drive, receive, and monitor traffic on AXI stream interfaces.  The `AxiStreamSource` drives all signals except for `tready` and can be used to drive AXI stream traffic into a design.  The `AxiStreamSink` drives the `tready` line only and as such can receive AXI stream traffic and exert backpressure.  The `AxiStreamMonitor` drives no signals and as such can be connected to internal AXI stream interfaces to monitor traffic.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import AxiStreamSource, AxiStreamSink

    axis_source = AxiStreamSource(dut, "s_axis", dut.clk, dut.rst)
    axis_sink = AxiStreamSink(dut, "m_axis", dut.clk, dut.rst)
    axis_monitor = AxiStreamMonitor(dut.inst, "int_axis", dut.clk, dut.rst)

The modules use `cocotb.bus.Bus` internally to automatically connect to the corresponding signals in the bus, presuming they are named according to the AXI spec and have a common prefix.

To send data into a design with an `AxiStreamSource`, call `send()` or `write()`.  Accepted data types are iterables or `AxiStreamFrame` objects.  Call `wait()` to wait for the transmit operation to complete.  Example:

    axis_source.send(b'test data')
    await axis_source.wait()

To receive data with an `AxiStreamSink` or `AxiStreamMonitor`, call `recv()` or `read()`.  `recv()` is intended for use with a frame-oriented interface, and by default compacts `AxiStreamFrame`s before returning them.  `read()` is intended for non-frame-oriented streams.  Calling `read()` internally calls `recv()` for all frames currently in the queue, then compacts and coalesces `tdata` from all frames into a separate read queue, from which read data is returned.  All sideband data is discarded.  Call `wait()` to wait for new receive data.

    await axis_sink.wait()
    data = axis_sink.recv()

#### Signals

* `tdata`: data, required
* `tvalid`: qualifies all other signals; optional, assumed `1` when absent
* `tready`: indicates sink is ready for data; optional, assumed `1` when absent
* `tlast`: marks the last cycle of a frame; optional, assumed `1` when absent
* `tkeep`: qualifies data byte, data bus width must be evenly divisible by `tkeep` signal width; optional, assumed `1` when absent
* `tid`: ID signal, can be used for routing; optional, assumed `0` when absent
* `tdest`: destination signal, can be used for routing; optional, assumed `0` when absent
* `tuser`: additional user data; optional, assumed `0` when absent

#### Constructor parameters:

* _entity_: object that contains the AXI stream interface signals
* _name_: signal name prefix (e.g. for `m_axis_tdata`, the prefix is `m_axis`)
* _clock_: clock signal
* _reset_: reset signal (optional)

#### Attributes:

* _pause_: stall the interface (deassert `tready` or `tvalid`) (source/sink only)
* _queue_occupancy_bytes_: number of bytes in queue (all)
* _queue_occupancy_frames_: number of frames in queue (all)
* _queue_occupancy_limit_bytes_: max number of bytes in queue allowed before tready deassert (sink only)
* _queue_occupancy_limit_frames_: max number of frames in queue allowed before tready deassert (sink only)

#### Methods

* `send(frame)`: send _frame_ (source)
* `write(data)`: send _data_ (alias of send) (source)
* `recv(compact)`: receive a frame, optionally compact frame (sink/monitor)
* `read(count)`: read _count_ bytes from buffer (sink/monitor)
* `count()`: returns the number of items in the queue (all)
* `empty()`: returns _True_ if the queue is empty (all)
* `full()`: returns _True_ if the queue occupancy limits are met (sink)
* `idle()`: returns _True_ if no transfer is in progress (all) or if the queue is not empty (source)
* `wait(timeout=0, timeout_unit='ns')`: wait for idle (source) or frame received (sink/monitor)
* `set_pause_generator(generator)`: set generator for pause signal, generator will be advanced on every clock cycle (source/sink)
* `clear_pause_generator()`: remove generator for pause signal

#### AxiStreamFrame object

The `AxiStreamFrame` object is a container for a frame to be transferred via AXI stream.  The `tdata` field contains the packet data in the form of a list of bytes, a `bytearray` if the byte size is 8 bits or a `list` of `int`s otherwise.  `tkeep`, `tid`, `tdest`, and `tuser` can either be `None`, an `int`, or a `list` of `int`s.  

Attributes:

* `tdata`: bytes, bytearray, or list
* `tkeep`: tkeep field, optional; list, each entry qualifies the corresponding entry in `tdata`.  Can be used to insert gaps on the source side.
* `tid`: tid field, optional; int or list with one entry per `tdata`, last value used per cycle when sending.
* `tdest`: tdest field, optional; int or list with one entry per `tdata`, last value used per cycle when sending.
* `tuser`: tuser field, optional; int or list with one entry per `tdata`, last value used per cycle when sending.

Methods:

* `normalize()`: pack `tkeep`, `tid`, `tdest`, and `tuser` to the same length as `tdata`, replicating last element if necessary, initialize `tkeep` to list of `1` and `tid`, `tdest`, and `tuser` to list of `0` if not specified.
* `compact()`: remove `tdata`, `tid`, `tdest`, and `tuser` values based on `tkeep`, remove `tkeep`, compact `tid`, `tdest`, and `tuser` to an int if all values are identical.

### AXI signals

* Write address channel
    * `awid`: transaction ID
    * `awaddr`: address
    * `awlen`: burst length (cycles)
    * `awsize`: burst size (bytes/cycle)
    * `awburst`: burst type
    * `awlock`: lock type
    * `awcache`: cache control
    * `awprot`: protection bits
    * `awqos`: QoS field
    * `awregion`: region field
    * `awuser`: additional user sideband data
    * `awvalid`: valid signal, qualifies all channel fields
    * `awready`: ready signal, back-pressure from sink
* Write data channel
    * `wdata`: write data
    * `wstrb`: write strobe
    * `wlast`: end of burst flag
    * `wuser`: additional user sideband data
    * `wvalid`: valid signal, qualifies all channel fields
    * `wready`: ready signal, back-pressure from sink
* Write response channel
    * `bid`: transaction ID
    * `bresp`: write response
    * `buser`: additional user sideband data
    * `bvalid`: valid signal, qualifies all channel fields
    * `bready`: ready signal, back-pressure from sink
* Read address channel
    * `arid`: transaction ID
    * `araddr`: address
    * `arlen`: burst length (cycles)
    * `arsize`: burst size (bytes/cycle)
    * `arburst`: burst type
    * `arlock`: lock type
    * `arcache`: cache control
    * `arprot`: protection bits
    * `arqos`: QoS field
    * `arregion`: region field
    * `aruser`: additional user sideband data
    * `arvalid`: valid signal, qualifies all channel fields
    * `arready`: ready signal, back-pressure from sink
* Read data channel
    * `rid`: transaction ID
    * `rdata`: read data
    * `rresp`: read response
    * `rlast`: end of burst flag
    * `ruser`: additional user sideband data
    * `rvalid`: valid signal, qualifies all channel fields
    * `rready`: ready signal, back-pressure from sink

### AXI lite signals

* Write address channel
    * `awaddr`: address
    * `awprot`: protection bits
    * `awvalid`: valid signal, qualifies all channel fields
    * `awready`: ready signal, back-pressure from sink
* Write data channel
    * `wdata`: write data
    * `wstrb`: write strobe
    * `wvalid`: valid signal, qualifies all channel fields
    * `wready`: ready signal, back-pressure from sink
* Write response channel
    * `bresp`: write response
    * `bvalid`: valid signal, qualifies all channel fields
    * `bready`: ready signal, back-pressure from sink
* Read address channel
    * `araddr`: address
    * `arprot`: protection bits
    * `arvalid`: valid signal, qualifies all channel fields
    * `arready`: ready signal, back-pressure from sink
* Read data channel
    * `rdata`: read data
    * `rresp`: read response
    * `rvalid`: valid signal, qualifies all channel fields
    * `rready`: ready signal, back-pressure from sink

### AXI stream signals

* `tdata`: data
* `tvalid`: qualifies all other signals
* `tready`: indicates sink is ready for data
* `tlast`: marks the last cycle of a frame
* `tkeep`: qualifies data bytes in `tdata`
* `tid`: ID signal, can be used for routing
* `tdest`: destination signal, can be used for routing
* `tuser`: additional sideband data
