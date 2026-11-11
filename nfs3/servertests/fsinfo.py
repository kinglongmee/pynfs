from .base import *
from xdrdef.nfs3_pack import NFS3Packer, NFS3Unpacker
from xdrdef.nfs3_type import FSINFO3args, nfs_fh3


class FsinfoTests:
    def test_fsinfo(self):
        result = self.call("FSINFO", FSINFO3args(self.root))
        if min(result.rtmax, result.rtpref, result.rtmult,
               result.wtmax, result.wtpref, result.wtmult,
               result.dtpref, result.maxfilesize) <= 0:
            raise AssertionError("FSINFO returned a non-positive limit")
        if result.time_delta.nseconds >= 1000000000:
            raise AssertionError("FSINFO returned an invalid time_delta")


    def edge_fsinfo_limits(self):
        result = self.call("FSINFO", FSINFO3args(self.root))
        if result.rtpref > result.rtmax or result.wtpref > result.wtmax:
            raise AssertionError("FSINFO preferred transfer exceeds maximum")
        if result.time_delta.nseconds >= 1000000000:
            raise AssertionError("FSINFO time_delta nanoseconds are out of range")
        if result.properties & ~(FSF3_LINK | FSF3_SYMLINK |
                                 FSF3_HOMOGENEOUS | FSF3_CANSETTIME):
            raise AssertionError("FSINFO returned undefined property bits")

    def test_fsinfo_argument_roundtrip(self):
        packer = NFS3Packer()
        packer.pack_FSINFO3args(FSINFO3args(nfs_fh3(b"test-handle")))
        unpacker = NFS3Unpacker(packer.get_buffer())
        args = unpacker.unpack_FSINFO3args()
        unpacker.done()
        if args.fsroot.data != b"test-handle":
            raise AssertionError("FSINFO XDR argument did not round-trip")
