"""REMOVEXATTR tests for the OpenFS NFSv3 xattr extension."""

from .getxattr import (
    CREATE, GETXATTR, LISTXATTR, REMOVEXATTR, SETXATTR, XattrTestBase)
from xdrdef.nfs3_const import NFS3ERR_NOENT


class RemovexattrTests(XattrTestBase):
    def test_removexattr(self):
        filename, handle = self._xattr_file("removexattr")
        key = b"user.pynfs.remove"
        try:
            self._xattr_call(REMOVEXATTR, handle, key, expected=NFS3ERR_NOENT)
            self._xattr_call(SETXATTR, handle, key, b"value", CREATE)
            self._xattr_call(REMOVEXATTR, handle, key)
            self._xattr_call(GETXATTR, handle, key, expected=NFS3ERR_NOENT)
            self._xattr_call(REMOVEXATTR, handle, key, expected=NFS3ERR_NOENT)
            _, eof, names = self._xattr_call(LISTXATTR, handle)
            if not eof or key in names:
                raise AssertionError("removed attribute remains in LISTXATTR")
        finally:
            self._unlink(filename)
