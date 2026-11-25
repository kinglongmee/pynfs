"""SETXATTR tests for the OpenFS NFSv3 xattr extension."""

from .getxattr import (
    CREATE, EITHER, GETXATTR, REPLACE, SETXATTR, XattrTestBase)
from xdrdef.nfs3_const import NFS3ERR_EXIST, NFS3ERR_NOENT, NFS3ERR_INVAL
from xdrdef.nfs3_pack import NFS3Packer


class SetxattrTests(XattrTestBase):
    def test_setxattr(self):
        filename, handle = self._xattr_file("setxattr")
        key = b"user.pynfs.set"
        try:
            self._xattr_call(SETXATTR, handle, key, b"missing", REPLACE,
                             expected=NFS3ERR_NOENT)
            self._xattr_call(SETXATTR, handle, key, b"first", CREATE)
            self._xattr_call(SETXATTR, handle, key, b"duplicate", CREATE,
                             expected=NFS3ERR_EXIST)
            if self._xattr_call(GETXATTR, handle, key) != b"first":
                raise AssertionError("failed CREATE changed the value")
            for option, value in ((REPLACE, b"second"), (EITHER, b"third")):
                self._xattr_call(SETXATTR, handle, key, value, option)
                if self._xattr_call(GETXATTR, handle, key) != value:
                    raise AssertionError("SETXATTR did not update the value")
            other = b"user.pynfs.either"
            self._xattr_call(SETXATTR, handle, other, b"", EITHER)
            if self._xattr_call(GETXATTR, handle, other) != b"":
                raise AssertionError("SETXATTR changed an empty value")
        finally:
            self._unlink(filename)

    def test_setxattr_invalid_option(self):
        filename, handle = self._xattr_file("setxattr-option")
        try:
            key = b"user.pynfs.invalid"
            value = b"value"
            for option in (3, 0xffffffff):
                self._xattr_call(SETXATTR, handle, key, value, option,
                                 expected=NFS3ERR_INVAL)
        finally:
            self._unlink(filename)
