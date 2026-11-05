from .base import *
from xdrdef.nfs3_const import *


class ReadlinkTests:
    def test_readlink(self):
        link = self._lookup(self.directory, b"seed-link")
        data = self.call("READLINK", READLINK3args(link)).data
        if data != LINK_DATA:
            raise AssertionError("READLINK returned %r" % data)


    def edge_readlink_wrong_type(self):
        self._expect_status("READLINK", READLINK3args(self.file),
                            [NFS3ERR_INVAL, NFS3ERR_NOTSUPP])


    def edge_readlink_long_target(self):
        name = self._name("longlink")
        target = b"/" + b"target/" * 64
        result = self.call("SYMLINK", SYMLINK3args(
            diropargs3(self.directory, name),
            symlinkdata3(unset_attributes(), target)))
        self.created_names.append(name)
        handle = self._lookup(self.directory, name)
        returned = self.call("READLINK", READLINK3args(handle)).data
        if returned != target:
            raise AssertionError("READLINK corrupted a long target")
        del result


    def edge_readlink_non_utf8_target(self):
        name = self._name("rawlink")
        target = b"relative-\xff-\xfe-\x80-target"
        self.call("SYMLINK", SYMLINK3args(
            diropargs3(self.directory, name),
            symlinkdata3(unset_attributes(), target)))
        self.created_names.append(name)
        handle = self._lookup(self.directory, name)
        returned = self.call("READLINK", READLINK3args(handle)).data
        if returned != target:
            raise AssertionError("READLINK changed a non-UTF-8 symlink target")

    def readlink_target(self):
        link = self._lookup(self.directory, b"seed-link")
        data = self.call("READLINK", READLINK3args(link)).data
        if data != LINK_DATA:
            raise AssertionError(
                "READLINK returned %r, expected %r" % (data, LINK_DATA))
