"""GETXATTR tests and shared helpers for the OpenFS NFSv3 xattr extension."""

import struct
from unittest.mock import Mock

import rpc.rpc as rpc
from xdrdef.nfs3_const import NFS3_OK, NFS3ERR_NOENT, nfsstat3
from xdrdef.nfs3_pack import NFS3Packer, NFS3Unpacker
from xdrdef.nfs3_type import nfs_fh3


GETXATTR, SETXATTR, LISTXATTR, REMOVEXATTR = 25, 26, 27, 28
EITHER, CREATE, REPLACE = 0, 1, 2


class XattrTestBase:
    def _xattr_call(self, procedure, handle, name=None, value=None, option=None,
                    cookie=0, maxcount=8192, expected=NFS3_OK):
        packer = NFS3Packer()
        packer.pack_nfs_fh3(handle)
        if procedure == SETXATTR:
            packer.pack_uint(option)
            packer.pack_string(name)
            packer.pack_string(value)
        elif procedure == LISTXATTR:
            packer.pack_uhyper(cookie)
            packer.pack_uint(maxcount)
        else:
            packer.pack_string(name)

        pipe = self.client.get_pipe()
        xid = self.client.send_call(
            pipe, procedure, packer.get_buffer(), self.client.default_cred)
        _, data = pipe.listen(xid, timeout=10.0)
        unpacker = NFS3Unpacker(data)
        status = unpacker.unpack_uint()
        if status != expected:
            raise AssertionError(
                "xattr procedure %d returned %s, expected %s" %
                (procedure, nfsstat3.get(status, status),
                 nfsstat3.get(expected, expected)))
        result = None
        if status == NFS3_OK:
            if procedure == GETXATTR:
                result = unpacker.unpack_string()
            elif procedure == LISTXATTR:
                next_cookie = unpacker.unpack_uhyper()
                eof = unpacker.unpack_bool()
                count = unpacker.unpack_uint()
                if count > (len(data) - unpacker.get_position()) // 4:
                    raise ValueError("truncated LISTXATTR names")
                names = [unpacker.unpack_string() for _ in range(count)]
                result = (next_cookie, eof, names)
            else:
                result = unpacker.unpack_wcc_data()
        unpacker.done()
        return result

    def _xattr_file(self, prefix):
        name = self._name(prefix)
        return name, self._create(name, mode=0o600)

    def _expect_xattr_garbage_args(self, procedure, payload):
        pipe = self.client.get_pipe()
        xid = self.client.send_call(
            pipe, procedure, payload, self.client.default_cred)
        try:
            pipe.listen(xid, timeout=10.0)
        except rpc.RPCAcceptError as error:
            if error.stat == rpc.GARBAGE_ARGS:
                return
            raise
        raise AssertionError(
            "xattr procedure %d accepted malformed arguments" % procedure)


class GetxattrTests(XattrTestBase):
    def test_getxattr(self):
        filename, handle = self._xattr_file("getxattr")
        other_filename, other_handle = self._xattr_file("getxattr-other")
        key = b"user.pynfs.get"
        try:
            self._xattr_call(GETXATTR, handle, key, expected=NFS3ERR_NOENT)
            for value in (b"", b"\x00\xffbinary\x00"):
                self._xattr_call(SETXATTR, handle, key, value, EITHER)
                if self._xattr_call(GETXATTR, handle, key) != value:
                    raise AssertionError("GETXATTR changed the attribute value")
            self._xattr_call(GETXATTR, other_handle, key,
                             expected=NFS3ERR_NOENT)
        finally:
            self._unlink(other_filename)
            self._unlink(filename)

    def test_xattr_wire(self):
        from . import NFS3Tests

        tests = object.__new__(NFS3Tests)
        tests.client = Mock()
        pipe = tests.client.get_pipe.return_value
        tests.client.send_call.return_value = 7
        handle = nfs_fh3(b"fh")
        fh = b"\0\0\0\2fh\0\0"
        name = b"\0\0\0\1k\0\0\0"
        ok = struct.pack(">I", NFS3_OK)
        cases = (
            (GETXATTR, {"name": b"k"}, fh + name,
             ok + b"\0\0\0\3v\0x\0", b"v\0x"),
            (SETXATTR, {"name": b"k", "value": b"v", "option": CREATE},
             fh + struct.pack(">I", CREATE) + name + b"\0\0\0\1v\0\0\0",
             ok + b"\0" * 8, None),
            (LISTXATTR, {"cookie": 0x100000002, "maxcount": 64},
             fh + struct.pack(">QI", 0x100000002, 64),
             ok + struct.pack(">QII", 9, 1, 2) + name +
             b"\0\0\0\2xy\0\0", (9, True, [b"k", b"xy"])),
            (REMOVEXATTR, {"name": b"k"}, fh + name, ok + b"\0" * 8, None),
        )
        for procedure, kwargs, payload, response, expected in cases:
            pipe.listen.return_value = (None, response)
            result = tests._xattr_call(procedure, handle, **kwargs)
            if expected is not None and result != expected:
                raise AssertionError("incorrect xattr response decoding")
            tests.client.send_call.assert_called_with(
                pipe, procedure, payload, tests.client.default_cred)
            pipe.listen.assert_called_with(7, timeout=10.0)

        pipe.listen.return_value = (None, struct.pack(">I", NFS3ERR_NOENT))
        tests._xattr_call(GETXATTR, handle, b"k", expected=NFS3ERR_NOENT)
        pipe.listen.return_value = (None, ok + struct.pack(">QII", 0, 1, 1))
        try:
            tests._xattr_call(LISTXATTR, handle)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted a truncated LISTXATTR reply")
