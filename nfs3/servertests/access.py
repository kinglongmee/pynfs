from .base import *
from xdrdef.nfs3_const import *


class AccessTests:
    def test_access(self):
        requested = ACCESS3_READ
        granted = self.call("ACCESS", ACCESS3args(self.file, requested)).access
        if granted & requested != requested:
            raise AssertionError("ACCESS did not grant READ on the test file")
        if granted & ~requested:
            raise AssertionError("ACCESS returned unrequested access bits")


    def edge_access_mask(self):
        requested = (ACCESS3_READ | ACCESS3_LOOKUP | ACCESS3_MODIFY |
                     ACCESS3_EXTEND | ACCESS3_DELETE | ACCESS3_EXECUTE)
        result = self.call("ACCESS", ACCESS3args(self.file, requested))
        if result.access & ~requested:
            raise AssertionError("ACCESS returned unrequested access bits")
        if not result.access & ACCESS3_READ:
            raise AssertionError("ACCESS did not grant READ on the seed file")


    def edge_access_unknown_bits(self):
        requested = 0xffffffff
        result = self.call("ACCESS", ACCESS3args(self.file, requested))
        valid = (ACCESS3_READ | ACCESS3_LOOKUP | ACCESS3_MODIFY |
                 ACCESS3_EXTEND | ACCESS3_DELETE | ACCESS3_EXECUTE)
        if result.access & ~valid:
            raise AssertionError("ACCESS returned undefined access bits")

    def access_all_combinations(self):
        valid = (ACCESS3_READ | ACCESS3_LOOKUP | ACCESS3_MODIFY |
                 ACCESS3_EXTEND | ACCESS3_DELETE | ACCESS3_EXECUTE)
        for requested in range(valid + 1):
            result = self.call("ACCESS", ACCESS3args(self.file, requested))
            if result.access & ~requested:
                raise AssertionError(
                    "ACCESS mask 0x%x returned unrequested bits 0x%x" %
                    (requested, result.access & ~requested))
