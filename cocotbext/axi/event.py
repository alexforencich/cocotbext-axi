from __future__ import annotations

import cocotb.triggers


class Event(cocotb.triggers.Event):
    def __init__(self):
        super().__init__()
        self._data: object | None = None

    @property
    def data(self) -> object:
        return self._data

    @data.setter
    def data(self, data: object) -> None:
        self._data = data

    def set(self, data: object | None = None) -> None:
        super().set()
        self._data = data

