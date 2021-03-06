from datetime import datetime

import attr

from dbnd._core.constants import _DbndDataClass


class Metric(_DbndDataClass):
    def __init__(
        self,
        key,
        timestamp,
        value_int=None,
        value_float=None,
        value_str=None,
        value=None,
    ):
        self.key = key
        self.timestamp = timestamp
        self.value_int = value_int
        self.value_float = value_float
        self.value_str = value_str
        self.value = value

    @property
    def value(self):
        if self.value_float is not None:
            return self.value_float
        if self.value_int is not None:
            return self.value_int
        return self.value_str

    @value.setter
    def value(self, value):
        if isinstance(value, float):
            self.value_float = value
        elif isinstance(value, int):
            self.value_int = value
        else:
            self.value_str = value


@attr.s
class Artifact(_DbndDataClass):
    path = attr.ib()  # type: str
