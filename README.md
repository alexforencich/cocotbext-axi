# AXI interface modules for Cocotb

[![Build Status](https://github.com/alexforencich/cocotbext-axi/workflows/Regression%20Tests/badge.svg?branch=master)](https://github.com/alexforencich/cocotbext-axi/actions/)
[![codecov](https://codecov.io/gh/alexforencich/cocotbext-axi/branch/master/graph/badge.svg)](https://codecov.io/gh/alexforencich/cocotbext-axi)
[![PyPI version](https://badge.fury.io/py/cocotbext-axi.svg)](https://pypi.org/project/cocotbext-axi)
[![Downloads](https://pepy.tech/badge/cocotbext-axi)](https://pepy.tech/project/cocotbext-axi)

GitHub repository: https://github.com/alexforencich/cocotbext-axi

## Introduction

AXI, AXI lite, and AXI stream simulation models for [cocotb](https://github.com/cocotb/cocotb).

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

The `AxiMaster` and `AxiLiteMaster` classes implement AXI masters and are capable of generating read and write operations against AXI slaves.  Requested operations will be split and aligned according to the AXI specification.  The `AxiMaster` module is capable of generating narrow bursts, handling multiple in-flight operations, and handling reordering and interleaving in responses across different transaction IDs.  `AxiMaster` and `AxiLiteMaster` and related objects all extend `Region`, so they can be attached to `AddressSpace` objects to handle memory operations in the specified region.

The `AxiMaster` is a wrapper around `AxiMasterWrite` and `AxiMasterRead`.  Similarly, `AxiLiteMaster` is a wrapper around `AxiLiteMasterWrite` and `AxiLiteMasterRead`.  If a read-only or write-only interface is required instead of a full interface, use the corresponding read-only or write-only variant, the usage and API are exactly the same.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import AxiBus, AxiMaster

    axi_master = AxiMaster(AxiBus.from_prefix(dut, "s_axi"), dut.clk, dut.rst)

The first argument to the constructor accepts an `AxiBus` or `AxiLiteBus` object, as appropriate.  These objects are containers for the interface signals and include class methods to automate connections.

Once the module is instantiated, read and write operations can be initiated in a couple of different ways.

First, operations can be carried out with async blocking `read()`, `write()`, and their associated word-access wrappers.  Multiple concurrent operations started from different coroutines are handled correctly, with results returned in the order that the operations complete.  For example:

    await axi_master.write(0x0000, b'test')
    data = await axi_master.read(0x0000, 4)

Additional parameters can be specified to control sideband signals and burst settings.  The transfer will be split into one or more bursts according to the AXI specification.  All bursts generated from the same call to `read()` or `write()` will use the same ID, which will be automatically generated if not specified.  `read()` and `write()` return `namedtuple` objects containing _address_, _data_ or _length_, and _resp_.  This is the preferred style, and this is the only style supported by the word-access wrappers.

Alternatively, operations can be initiated with non-blocking `init_read()` and `init_write()`.  These functions return `Event` objects which are triggered when the operation completes, and the result can be retrieved from `Event.data`.  For example:

    write_op = axi_master.init_write(0x0000, b'test')
    await write_op.wait()
    resp = write_op.data
    read_op = axi_master.init_read(0x0000, 4)
    await read_op.wait()
    resp = read_op.data

With this method, it is possible to start multiple concurrent operations from the same coroutine.  It is also possible to use the events with `Combine`, `First`, and `with_timeout`.

#### `AxiMaster` and `AxiLiteMaster` constructor parameters

* _bus_: `AxiBus` or `AxiLiteBus` object containing AXI interface signals
* _clock_: clock signal
* _reset_: reset signal (optional)
* _reset_active_level_: reset active level (optional, default `True`)

#### Additional parameters for `AxiMaster`

* _max_burst_len_: maximum burst length in cycles, range 1-256, default 256.

#### Methods

* `init_read(address, length, ...)`: initiate reading _length_ bytes, starting at _address_.  Returns an `Event` object.
* `init_write(address, data, ...)`: initiate writing _data_ (bytes), starting from _address_.  Returns an `Event` object.
* `idle()`: returns _True_ when there are no outstanding operations in progress
* `wait()`: blocking wait until all outstanding operations complete
* `wait_read()`: wait until all outstanding read operations complete
* `wait_write()`: wait until all outstanding write operations complete
* `read(address, length, ...)`: read _length_ bytes, starting at _address_
* `read_words(address, count, byteorder='little', ws=2, ...)`: read _count_ _ws_-byte words, starting at _address_
* `read_dwords(address, count, byteorder='little', ...)`: read _count_ 4-byte dwords, starting at _address_
* `read_qwords(address, count, byteorder='little', ...)`: read _count_ 8-byte qwords, starting at _address_
* `read_byte(address, ...)`: read single byte at _address_
* `read_word(address, byteorder='little', ws=2, ...)`: read single _ws_-byte word at _address_
* `read_dword(address, byteorder='little', ...)`: read single 4-byte dword at _address_
* `read_qword(address, byteorder='little', ...)`: read single 8-byte qword at _address_
* `write(address, data, ...)`: write _data_ (bytes), starting at _address_
* `write_words(address, data, byteorder='little', ws=2, ...)`: write _data_ (_ws_-byte words), starting at _address_
* `write_dwords(address, data, byteorder='little', ...)`: write _data_ (4-byte dwords), starting at _address_
* `write_qwords(address, data, byteorder='little', ...)`: write _data_ (8-byte qwords), starting at _address_
* `write_byte(address, data, ...)`: write single byte at _address_
* `write_word(address, data, byteorder='little', ws=2, ...)`: write single _ws_-byte word at _address_
* `write_dword(address, data, byteorder='little', ...)`: write single 4-byte dword at _address_
* `write_qword(address, data, byteorder='little', ...)`: write single 8-byte qword at _address_

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
* _event_: `Event` object used to wait on and retrieve result for specific operation, default `None`.  The event will be triggered when the operation completes and the result returned via `Event.data`.  (`init_read()` and `init_write()` only)

#### Additional optional arguments for `AxiLiteMaster`

* _prot_: AXI protection flags, default `AxiProt.NONSECURE`
* _event_: `Event` object used to wait on and retrieve result for specific operation, default `None`.  The event will be triggered when the operation completes and the result returned via `Event.data`.  (`init_read()` and `init_write()` only)

#### `AxiBus` and `AxiLiteBus` objects

The `AxiBus`, `AxiLiteBus`, and related objects are containers for the interface signals.  These hold instances of bus objects for the individual channels, which are currently extensions of `cocotb_bus.bus.Bus`.  Class methods `from_entity` and `from_prefix` are provided to facilitate signal name matching.  For AXI interfaces use `AxiBus`, `AxiReadBus`, or `AxiWriteBus`, as appropriate.  For AXI lite interfaces, use `AxiLiteBus`, `AxiLiteReadBus`, or `AxiLiteWriteBus`, as appropriate.

### AXI and AXI lite slave

The `AxiSlave` and `AxiLiteSlave` classes implement AXI slaves and are capable of completing read and write operations from upstream AXI masters.  The `AxiSlave` module is capable of handling narrow bursts.  These modules can either be used to perform memory reads and writes on a `MemoryInterface` on behalf of the DUT, or they can be extended to implement customized functionality.

The `AxiSlave` is a wrapper around `AxiSlaveWrite` and `AxiSlaveRead`.  Similarly, `AxiLiteSlave` is a wrapper around `AxiLiteSlaveWrite` and `AxiLiteSlaveRead`.  If a read-only or write-only interface is required instead of a full interface, use the corresponding read-only or write-only variant, the usage and API are exactly the same.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import AxiBus, AxiSlave, MemoryRegion

    axi_slave = AxiSlave(AxiBus.from_prefix(dut, "m_axi"), dut.clk, dut.rst)
    region = MemoryRegion(2**axi_slave.read_if.address_width)
    axi_slave.target = region

The first argument to the constructor accepts an `AxiBus` or `AxiLiteBus` object.  These objects are containers for the interface signals and include class methods to automate connections.

It is also possible to extend these modules; operation can be customized by overriding the internal `_read()` and `_write()` methods.  See `AxiRam` and `AxiLiteRam` for an example.

#### `AxiSlave` and `AxiLiteSlave` constructor parameters

* _bus_: `AxiBus` or `AxiLiteBus` object containing AXI interface signals
* _clock_: clock signal
* _reset_: reset signal (optional)
* _reset_active_level_: reset active level (optional, default `True`)
* _target_: target region (optional, default `None`)

#### Attributes:

* _target_: target region

### AXI and AXI lite RAM

The `AxiRam` and `AxiLiteRam` classes implement AXI RAMs and are capable of completing read and write operations from upstream AXI masters.  The `AxiRam` module is capable of handling narrow bursts.  These modules are extensions of the corresponding `AxiSlave` and `AxiLiteSlave` modules.  Internally, `SparseMemory` is used to support emulating very large memories.

The `AxiRam` is a wrapper around `AxiRamWrite` and `AxiRamRead`.  Similarly, `AxiLiteRam` is a wrapper around `AxiLiteRamWrite` and `AxiLiteRamRead`.  If a read-only or write-only interface is required instead of a full interface, use the corresponding read-only or write-only variant, the usage and API are exactly the same.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import AxiBus, AxiRam

    axi_ram = AxiRam(AxiBus.from_prefix(dut, "m_axi"), dut.clk, dut.rst, size=2**32)

The first argument to the constructor accepts an `AxiBus` or `AxiLiteBus` object.  These objects are containers for the interface signals and include class methods to automate connections.

Once the module is instantiated, the memory contents can be accessed in a couple of different ways.  First, the `mmap` object can be accessed directly via the `mem` attribute.  Second, `read()`, `write()`, and various word-access wrappers are available.  Hex dump helper methods are also provided for debugging.  For example:

    axi_ram.write(0x0000, b'test')
    data = axi_ram.read(0x0000, 4)
    axi_ram.hexdump(0x0000, 4, prefix="RAM")

Multi-port memories can be constructed by passing the `mem` object of the first instance to the other instances.  For example, here is how to create a four-port RAM:

    axi_ram_p1 = AxiRam(AxiBus.from_prefix(dut, "m00_axi"), dut.clk, dut.rst, size=2**32)
    axi_ram_p2 = AxiRam(AxiBus.from_prefix(dut, "m01_axi"), dut.clk, dut.rst, mem=axi_ram_p1.mem)
    axi_ram_p3 = AxiRam(AxiBus.from_prefix(dut, "m02_axi"), dut.clk, dut.rst, mem=axi_ram_p1.mem)
    axi_ram_p4 = AxiRam(AxiBus.from_prefix(dut, "m03_axi"), dut.clk, dut.rst, mem=axi_ram_p1.mem)

#### `AxiRam` and `AxiLiteRam` constructor parameters

* _bus_: `AxiBus` or `AxiLiteBus` object containing AXI interface signals
* _clock_: clock signal
* _reset_: reset signal (optional)
* _reset_active_level_: reset active level (optional, default `True`)
* _size_: memory size in bytes (optional, default `2**64`)
* _mem_: `mmap` or `SparseMemory` backing object to use (optional, overrides _size_)

#### Attributes:

* _mem_: directly access shared `mmap` or `SparseMemory` backing object

#### Methods

* `read(address, length)`: read _length_ bytes, starting at _address_
* `read_words(address, count, byteorder='little', ws=2)`: read _count_ _ws_-byte words, starting at _address_
* `read_dwords(address, count, byteorder='little')`: read _count_ 4-byte dwords, starting at _address_
* `read_qwords(address, count, byteorder='little')`: read _count_ 8-byte qwords, starting at _address_
* `read_byte(address)`: read single byte at _address_
* `read_word(address, byteorder='little', ws=2)`: read single _ws_-byte word at _address_
* `read_dword(address, byteorder='little')`: read single 4-byte dword at _address_
* `read_qword(address, byteorder='little')`: read single 8-byte qword at _address_
* `write(address, data)`: write _data_ (bytes), starting at _address_
* `write_words(address, data, byteorder='little', ws=2)`: write _data_ (_ws_-byte words), starting at _address_
* `write_dwords(address, data, byteorder='little')`: write _data_ (4-byte dwords), starting at _address_
* `write_qwords(address, data, byteorder='little')`: write _data_ (8-byte qwords), starting at _address_
* `write_byte(address, data)`: write single byte at _address_
* `write_word(address, data, byteorder='little', ws=2)`: write single _ws_-byte word at _address_
* `write_dword(address, data, byteorder='little')`: write single 4-byte dword at _address_
* `write_qword(address, data, byteorder='little')`: write single 8-byte qword at _address_
* `hexdump(address, length, prefix='')`: print hex dump of _length_ bytes starting from _address_, prefix lines with optional _prefix_
* `hexdump_line(address, length, prefix='')`: return hex dump (list of str) of _length_ bytes starting from _address_, prefix lines with optional _prefix_
* `hexdump_str(address, length, prefix='')`: return hex dump (str) of _length_ bytes starting from _address_, prefix lines with optional _prefix_

### AXI stream

The `AxiStreamSource`, `AxiStreamSink`, and `AxiStreamMonitor` classes can be used to drive, receive, and monitor traffic on AXI stream interfaces.  The `AxiStreamSource` drives all signals except for `tready` and can be used to drive AXI stream traffic into a design.  The `AxiStreamSink` drives the `tready` line only and as such can receive AXI stream traffic and exert backpressure.  The `AxiStreamMonitor` drives no signals and as such can be connected to AXI stream interfaces anywhere within a design to passively monitor traffic.

To use these modules, import the one you need and connect it to the DUT:

    from cocotbext.axi import (AxiStreamBus, AxiStreamSource, AxiStreamSink, AxiStreamMonitor)

    axis_source = AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.clk, dut.rst)
    axis_sink = AxiStreamSink(AxiStreamBus.from_prefix(dut, "m_axis"), dut.clk, dut.rst)
    axis_mon= AxiStreamMonitor(AxiStreamBus.from_prefix(dut.inst, "int_axis"), dut.clk, dut.rst)

The first argument to the constructor accepts an `AxiStreamBus` object.  This object is a container for the interface signals and includes class methods to automate connections.

To send data into a design with an `AxiStreamSource`, call `send()`/`send_nowait()` or `write()`/`write_nowait()`.  Accepted data types are iterables or `AxiStreamFrame` objects.  Optionally, call `wait()` to wait for the transmit operation to complete.  Example:

    await axis_source.send(b'test data')
    # wait for operation to complete (optional)
    await axis_source.wait()

It is also possible to wait for the transmission of a specific frame to complete by passing an event in the tx_complete field of the `AxiStreamFrame` object, and then awaiting the event.  The frame, with simulation time fields set, will be returned in the event data.  Example:

    frame = AxiStreamFrame(b'test data', tx_complete=Event())
    await axis_source.send(frame)
    await frame.tx_complete.wait()
    print(frame.tx_complete.data.sim_time_start)

To receive data with an `AxiStreamSink` or `AxiStreamMonitor`, call `recv()`/`recv_nowait()` or `read()`/`read_nowait()`.  Optionally call `wait()` to wait for new receive data.  `recv()` is intended for use with a frame-oriented interface, and by default compacts `AxiStreamFrame`s before returning them.  `read()` is intended for non-frame-oriented streams.  Calling `read()` internally calls `recv()` for all frames currently in the queue, then compacts and coalesces `tdata` from all frames into a separate read queue, from which read data is returned.  All sideband data is discarded.

    data = await axis_sink.recv()

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

* _bus_: `AxiStreamBus` object containing AXI stream interface signals
* _clock_: clock signal
* _reset_: reset signal (optional)
* _reset_active_level_: reset active level (optional, default `True`)
* _byte_size_: byte size (optional)
* _byte_lanes_: byte lane count (optional)

Note: _byte_size_, _byte_lanes_, `len(tdata)`, and `len(tkeep)` are all related, in that _byte_lanes_ is set from `tkeep` if it is connected, and `byte_size*byte_lanes == len(tdata)`.  So, if `tkeep` is connected, both _byte_size_ and _byte_lanes_ will be computed internally and cannot be overridden.  If `tkeep` is not connected, then either _byte_size_ or _byte_lanes_ can be specified, and the other will be computed such that `byte_size*byte_lanes == len(tdata)`.

#### Attributes:

* _pause_: stall the interface (deassert `tready` or `tvalid`) (source/sink only)
* _queue_occupancy_bytes_: number of bytes in queue (all)
* _queue_occupancy_frames_: number of frames in queue (all)
* _queue_occupancy_limit_bytes_: max number of bytes in queue allowed before backpressure is applied (source/sink only)
* _queue_occupancy_limit_frames_: max number of frames in queue allowed before backpressure is applied (source/sink only)

#### Methods

* `send(frame)`: send _frame_ (blocking) (source)
* `send_nowait(frame)`: send _frame_ (non-blocking) (source)
* `write(data)`: send _data_ (alias of send) (blocking) (source)
* `write_nowait(data)`: send _data_ (alias of send_nowait) (non-blocking) (source)
* `recv(compact=True)`: receive a frame as a `GmiiFrame` (blocking) (sink)
* `recv_nowait(compact=True)`: receive a frame as a `GmiiFrame` (non-blocking) (sink)
* `read(count)`: read _count_ bytes from buffer (blocking) (sink/monitor)
* `read_nowait(count)`: read _count_ bytes from buffer (non-blocking) (sink/monitor)
* `count()`: returns the number of items in the queue (all)
* `empty()`: returns _True_ if the queue is empty (all)
* `full()`: returns _True_ if the queue occupancy limits are met (source/sink)
* `idle()`: returns _True_ if no transfer is in progress (all) or if the queue is not empty (source)
* `clear()`: drop all data in queue (all)
* `wait()`: wait for idle (source)
* `wait(timeout=0, timeout_unit='ns')`: wait for frame received (sink)
* `set_pause_generator(generator)`: set generator for pause signal, generator will be advanced on every clock cycle (source/sink)
* `clear_pause_generator()`: remove generator for pause signal (source/sink)

#### `AxiStreamBus` object

The `AxiStreamBus` object is a container for the interface signals.  Currently, it is an extension of `cocotb.bus.Bus`.  Class methods `from_entity` and `from_prefix` are provided to facilitate signal name matching.

#### `AxiStreamFrame` object

The `AxiStreamFrame` object is a container for a frame to be transferred via AXI stream.  The `tdata` field contains the packet data in the form of a list of bytes, which is either a `bytearray` if the byte size is 8 bits or a `list` of `int`s otherwise.  `tkeep`, `tid`, `tdest`, and `tuser` can either be `None`, an `int`, or a `list` of `int`s.

Attributes:

* `tdata`: bytes, bytearray, or list
* `tkeep`: tkeep field, optional; list, each entry qualifies the corresponding entry in `tdata`.  Can be used to insert gaps on the source side.
* `tid`: tid field, optional; int or list with one entry per `tdata`, last value used per cycle when sending.
* `tdest`: tdest field, optional; int or list with one entry per `tdata`, last value used per cycle when sending.
* `tuser`: tuser field, optional; int or list with one entry per `tdata`, last value used per cycle when sending.
* `sim_time_start`: simulation time of first transfer cycle of frame.
* `sim_time_end`: simulation time of last transfer cycle of frame.
* `tx_complete`: event or callable triggered when frame is transmitted.

Methods:

* `normalize()`: pack `tkeep`, `tid`, `tdest`, and `tuser` to the same length as `tdata`, replicating last element if necessary, initialize `tkeep` to list of `1` and `tid`, `tdest`, and `tuser` to list of `0` if not specified.
* `compact()`: remove `tdata`, `tid`, `tdest`, and `tuser` values based on `tkeep`, remove `tkeep`, compact `tid`, `tdest`, and `tuser` to an int if all values are identical.

### Address space abstraction

The address space abstraction provides a framework for cross-connecting multiple memory-mapped interfaces for testing components that interface with complex systems, including components with DMA engines.

`MemoryInterface` is the base class for all components in the address space abstraction.  `MemoryInterface` provides the core `read()` and `write()` methods, which implement bounds checking, as well as word-access wrappers.  Methods for creating `Window` and `WindowPool` objects are also provided.  The function `get_absolute_address()` translates addresses to the system address space.  `MemoryInterface` can be extended to implement custom functionality by overriding `_read()` and `_write()`.

`Window` objects represent views onto a parent address space with some length and offset.  `read()` and `write()` operations on a `Window` are translated to the equivalent operations on the parent address space.  Multiple `Window` instances can overlap and access the same portion of address space.

`WindowPool` provides a method for dynamically allocating windows from a section of address space.  It uses a standard memory management algorithm to provide naturally-aligned `Window` objects of the requested size.

`Region` is the base class for all components which implement a portion of address space.  `Region` objects can be registered with `AddressSpace` objects to handle `read()` and `write()` operations in a specified region.  `Region` can be extended by components that implement a portion of address space.

`MemoryRegion` is an extension of `Region` that uses an `mmap` instance to handle memory operations.  `MemoryRegion` also provides hex dump methods as well as indexing and slicing.

`SparseMemoryRegion` is similar to `MemoryRegion` but is backed by `SparseMemory` instead of `mmap` and as such can emulate extremely large regions of address space.

`PeripheralRegion` is an extension of `Region` that can wrap another object that implements `read()` and `write()`, as an alternative to extending `Region`.

`AddressSpace` is the core object for handling address spaces.  `Region` objects can be registered with `AddressSpace` with specified base address, size, and offset.  The `AddressSpace` object will then direct `read()` and `write()` operations to the appropriate `Region`s, splitting requests appropriately when necessary and translating addresses.  Regions registered with `offset` other than `None` are translated such that accesses to base address + N map to N + offset.  Regions registered with an `offset` of `None` are not translated.  `Region` objects registered with the same `AddressSpace` cannot overlap, however the same `Region` can be registered multiple times.  `AddressSpace` also provides a method for creating `Pool` objects.

`Pool` is an extension of `AddressSpace` that supports dynamic allocation of `MemoryRegion`s.  It uses a standard memory management algorithm to provide naturally-aligned `MemoryRegion` objects of the requested size.

#### Example

This is a simple example that shows how the address space abstraction components can be used to connect a DUT to a simulated host system, including simulated RAM, an AXI interface from the DUT for DMA, and an AXI lite interface to the DUT for control.

    from cocotbext.axi import AddressSpace, SparseMemoryRegion
    from cocotbext.axi import AxiBus, AxiLiteMaster, AxiSlave

    # system address space
    address_space = AddressSpace(2**32)

    # RAM
    ram = SparseMemoryRegion(2**24)
    address_space.register_region(ram, 0x0000_0000)
    ram_pool = address_space.create_window_pool(0x0000_0000, 2**20)

    # DUT control register interface
    axil_master = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axil_ctrl"), dut.clk, dut.rst)
    address_space.register_region(axil_master, 0x8000_0000)
    ctrl_regs = address_space.create_window(0x8000_0000, axil_master.size)

    # DMA from DUT
    axi_slave = AxiSlave(AxiBus.from_prefix(dut, "m_axi_dma"), dut.clk, dut.rst, target=address_space)

    # exercise DUT DMA functionality
    src_block = ram_pool.alloc_window(1024)
    dst_block = ram_pool.alloc_window(1024)

    test_data = b'test data'
    await src_block.write(0, test_data)

    await ctrl_regs.write_dword(DMA_SRC_ADDR, src_block.get_absolute_address(0))
    await ctrl_regs.write_dword(DMA_DST_ADDR, dst_block.get_absolute_address(0))
    await ctrl_regs.write_dword(DMA_LEN, len(test_data))
    await ctrl_regs.write_dword(DMA_CONTROL, 1)

    while await ctrl_regs.read_dword(DMA_STATUS) == 0:
        pass

    assert await dst_block.read(0, len(test_data)) == test_data

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
