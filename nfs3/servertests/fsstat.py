from .base import *


class FsstatTests:
    def test_fsstat(self):
        result = self.call("FSSTAT", FSSTAT3args(self.root))
        if result.tbytes < result.fbytes or result.tfiles < result.ffiles:
            raise AssertionError("FSSTAT returned inconsistent totals")


    def edge_fsstat_counts(self):
        result = self.call("FSSTAT", FSSTAT3args(self.root))
        if result.fbytes > result.tbytes or result.abytes > result.fbytes:
            raise AssertionError("FSSTAT byte counts are inconsistent")
        if result.ffiles > result.tfiles or result.afiles > result.ffiles:
            raise AssertionError("FSSTAT file counts are inconsistent")
