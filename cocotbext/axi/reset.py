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

import cocotb
from cocotb.triggers import RisingEdge, FallingEdge


class Reset:
    def _init_reset(self, reset_signal=None, active_level=True):
        self._local_reset = False
        self._ext_reset = False
        self._reset_state = True

        if reset_signal is not None:
            cocotb.start_soon(self._run_reset(reset_signal, bool(active_level)))

        self._update_reset()

    def assert_reset(self, val=None):
        if val is None:
            self.assert_reset(True)
            self.assert_reset(False)
        else:
            self._local_reset = bool(val)
            self._update_reset()

    def _update_reset(self):
        new_state = self._local_reset or self._ext_reset
        if self._reset_state != new_state:
            self._reset_state = new_state
            self._handle_reset(new_state)

    def _handle_reset(self, state):
        pass

    async def _run_reset(self, reset_signal, active_level):
        while True:
            if bool(reset_signal.value):
                await FallingEdge(reset_signal)
                self._ext_reset = not active_level
                self._update_reset()
            else:
                await RisingEdge(reset_signal)
                self._ext_reset = active_level
                self._update_reset()
