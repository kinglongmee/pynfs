from .base import *
from xdrdef.nfs3_const import *


class CommitTests:
    def test_commit(self):
        write = self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), UNSTABLE, TEST_DATA))
        commit = self.call("COMMIT", COMMIT3args(self.file, 0, 0))
        if write.verf != commit.verf:
            raise AssertionError("COMMIT write verifier differs from WRITE")


    def edge_commit_range(self):
        for offset, count in ((1, 1), (0, 0xffffffff),
                              (0xffffffffffffffff, 0)):
            self.call("COMMIT", COMMIT3args(self.file, offset, count))

    def commit_written_data(self):
        name = self._name("commit-written")
        handle = self._create(name, mode=0o600)
        data = b"commit test data"
        try:
            write = self.call(
                "WRITE", WRITE3args(handle, 0, len(data), UNSTABLE, data))
            commit = self.call("COMMIT", COMMIT3args(handle, 0, 0))
            if len(commit.verf) != NFS3_WRITEVERFSIZE:
                raise AssertionError(
                    "COMMIT returned a verifier of invalid length")
            read = self.call("READ", READ3args(handle, 0, len(data)))
            if read.data != data:
                raise AssertionError("COMMIT data was not readable")
            if write.count != len(data):
                raise AssertionError(
                    "UNSTABLE WRITE returned an incorrect count")
        finally:
            self._unlink(name)
