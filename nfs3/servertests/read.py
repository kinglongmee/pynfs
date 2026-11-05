from .base import *
from xdrdef.nfs3_const import *


class ReadTests:
    def test_read(self):
        result = self.call("READ", READ3args(self.file, 0, len(TEST_DATA)))
        if result.count != len(TEST_DATA) or result.data != TEST_DATA or \
                not result.eof:
            raise AssertionError("READ returned incomplete or unexpected data")


    def edge_read_zero_count(self):
        result = self.call("READ", READ3args(self.file, 0, 0))
        if result.count != 0 or result.data:
            raise AssertionError("zero-count READ returned data")


    def edge_read_beyond_eof(self):
        size = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes.size
        result = self.call("READ", READ3args(self.file, size + 4096, 32))
        if result.count != 0 or result.data or not result.eof:
            raise AssertionError("READ beyond EOF returned unexpected data")


    def edge_read_max_count(self):
        result = self.call("READ", READ3args(self.file, 0, 0xffffffff))
        if result.data != TEST_DATA or result.count != len(TEST_DATA) or \
                not result.eof:
            raise AssertionError("READ with maximum count returned unexpected data")

    def read_file_data(self):
        result = self.call(
            "READ", READ3args(self.file, 0, len(TEST_DATA) + 1))
        if result.data != TEST_DATA or not result.eof:
            raise AssertionError("READ returned incorrect data or EOF status")

    def read_past_end_of_file(self):
        result = self.call("READ", READ3args(self.file, 1 << 20, 32))
        if result.data or not result.eof:
            raise AssertionError(
                "READ beyond EOF should return empty data and eof=true")
