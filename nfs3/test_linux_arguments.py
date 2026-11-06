"""Offline checks for Linux nfsd argument-validation cases."""

import os
import struct
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "nfs4.1"))

from nfs3.testcases import NFS3Tests, rpc
from xdrdef.nfs3_pack import NFS3Unpacker
from xdrdef.nfs3_type import nfs_fh3


LINUX_CASES = [c for c in NFS3Tests.edge_cases if c[0].startswith("LINUX_")]


class LinuxArgumentTests(unittest.TestCase):
    def setUp(self):
        self.tests = object.__new__(NFS3Tests)
        self.tests.directory = nfs_fh3(b"directory")
        self.tests.file = nfs_fh3(b"file")
        self.tests._serial = 0
        self.tests.client = Mock()

    def test_name_matrix_reaches_both_rename_arguments(self):
        self.tests._expect_garbage_args = Mock()
        self.tests.linux_invalid_names()
        calls = self.tests._expect_garbage_args.call_args_list
        self.assertEqual(len(calls), 40)
        rename_names = []
        for call in calls:
            procedure, payload = call[0]
            if procedure == "RENAME":
                unpacker = NFS3Unpacker(payload)
                args = unpacker.unpack_RENAME3args()
                unpacker.done()
                rename_names.append((args.fromfile.name, args.tofile.name))
        invalid = (b"", b"x" * 256, b"nul\0name", b"slash/name")
        self.assertEqual([pair[0] for pair in rename_names[::2]],
                         list(invalid))
        self.assertEqual([pair[1] for pair in rename_names[1::2]],
                         list(invalid))

    def test_write_count_mismatches_survive_encoding(self):
        self.tests._expect_garbage_args = Mock()
        self.tests.linux_write_count()
        calls = self.tests._expect_garbage_args.call_args_list
        self.assertEqual(len(calls), 4)
        for call in calls:
            procedure, payload = call[0]
            self.assertEqual(procedure, "WRITE")
            args = NFS3Unpacker(payload).unpack_WRITE3args()
            self.assertNotEqual(args.count, len(args.data))

    def test_handle_lengths_are_not_blocked_by_client_packer(self):
        self.tests._expect_garbage_args = Mock()
        self.tests.linux_handle_length()
        payloads = [call[0][1] for call in
                    self.tests._expect_garbage_args.call_args_list]
        self.assertEqual([struct.unpack(">I", p[:4])[0] for p in payloads],
                         [0, 65])

    def test_all_raw_cases_build_payloads(self):
        self.tests._expect_garbage_args = Mock()
        for _, _, method in LINUX_CASES:
            if method == "linux_mknod_badtype":
                continue
            with self.subTest(method=method):
                self.tests._expect_garbage_args.reset_mock()
                getattr(self.tests, method)()
                self.assertTrue(self.tests._expect_garbage_args.called)
                for call in self.tests._expect_garbage_args.call_args_list:
                    self.assertIsInstance(call[0][1], bytes)

    def test_garbage_args_is_the_only_accepted_rpc_error(self):
        pipe = self.tests.client.get_pipe.return_value
        error = rpc.RPCAcceptError.__new__(rpc.RPCAcceptError)
        error.stat = rpc.GARBAGE_ARGS
        pipe.listen.side_effect = error
        self.tests._expect_garbage_args("GETATTR", b"")
        error.stat = rpc.SYSTEM_ERR
        with self.assertRaises(rpc.RPCAcceptError):
            self.tests._expect_garbage_args("GETATTR", b"")

    def test_success_and_timeouts_do_not_pass(self):
        pipe = self.tests.client.get_pipe.return_value
        with self.assertRaisesRegex(AssertionError, "accepted malformed"):
            self.tests._expect_garbage_args("GETATTR", b"")
        pipe.listen.side_effect = rpc.RPCTimeout()
        with self.assertRaises(rpc.RPCTimeout):
            self.tests._expect_garbage_args("GETATTR", b"")


if __name__ == "__main__":
    unittest.main()
