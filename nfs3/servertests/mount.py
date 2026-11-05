"""Offline regression tests for the NFSv3 MOUNT client."""

import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "nfs4.1"))

from nfs3client import Mnt3Client, NFS3Client
from xdrdef.mnt3_const import MNT3_OK, MNT3ERR_ACCES, MOUNTPROC3_MNT
from xdrdef.mnt3_pack import MNT3Packer, MNT3Unpacker
from xdrdef.mnt3_type import mountres3, mountres3_ok
from xdrdef.nfs3_pack import NFS3Packer, NFS3Unpacker
from xdrdef.nfs3_type import FSINFOargs, nfs_fh3
from rpc.rpc import RPCError


class MountTests(unittest.TestCase):
    def mount(self, components, response):
        client = object.__new__(Mnt3Client)
        client.proc = Mock(return_value=response)
        handle = client.get_rootfh(components)
        proc, arg, result_type = client.proc.call_args[0]
        self.assertEqual(proc, MOUNTPROC3_MNT)
        self.assertEqual(result_type, "mountres3")
        packer = MNT3Packer()
        getattr(packer, "pack_" + arg.__class__.__name__)(arg)
        unpacker = MNT3Unpacker(packer.get_buffer())
        path = unpacker.unpack_dirpath()
        unpacker.done()
        self.assertEqual(handle, b"test-handle")
        return path

    def test_text_export_is_encoded_for_xdr(self):
        response = mountres3(MNT3_OK, mountres3_ok(b"test-handle", []))
        self.assertEqual(self.mount(["nfs/"], response), b"/nfs/")

    def test_byte_export_components_remain_supported(self):
        response = mountres3(MNT3_OK, mountres3_ok(b"test-handle", []))
        self.assertEqual(self.mount([b"nfs", b"subdir"], response),
                         b"/nfs/subdir")

    def test_mount_error_reports_status(self):
        client = object.__new__(Mnt3Client)
        client.proc = Mock(return_value=mountres3(MNT3ERR_ACCES))
        with self.assertRaisesRegex(RPCError, "MNT3ERR_ACCES"):
            client.get_rootfh(["nfs"])


class NFSClientTests(unittest.TestCase):
    def test_null_uses_empty_bytes(self):
        client = object.__new__(NFS3Client)
        client.get_pipe = Mock()
        client.send_call = Mock()
        client.null_async()
        client.send_call.assert_called_once_with(
            client.get_pipe.return_value, 0, b"")

    def test_fsinfo_argument_roundtrip(self):
        packer = NFS3Packer()
        packer.pack_FSINFOargs(FSINFOargs(nfs_fh3(b"test-handle")))
        unpacker = NFS3Unpacker(packer.get_buffer())
        args = unpacker.unpack_FSINFOargs()
        unpacker.done()
        self.assertEqual(args.fsroot.data, b"test-handle")


if __name__ == "__main__":
    unittest.main()
