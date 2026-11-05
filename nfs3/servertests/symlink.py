from .base import *


class SymlinkTests:
    def test_symlink(self):
        self._symlink(b"symlink-test")
        link = self._lookup(self.directory, b"symlink-test")
        if self.call("GETATTR", GETATTR3args(link)).obj_attributes.type != NF3LNK:
            raise AssertionError("SYMLINK did not create a symbolic link")


    def edge_symlink_dot_components(self):
        self._expect_dot_status(
            "SYMLINK", lambda where: SYMLINK3args(
                where, symlinkdata3(unset_attributes(), LINK_DATA)),
            [NFS3ERR_EXIST,NFS3ERR_INVAL])


    def edge_symlink_exist(self):
        name = self._name("symlink")
        self._symlink(name)
        self._expect_status(
            "SYMLINK",
            SYMLINK3args(diropargs3(self.directory, name),
                         symlinkdata3(unset_attributes(), LINK_DATA)),
            [NFS3ERR_EXIST])


    def symlink_truncated(self):
        payload = self._pack_args(SYMLINK3args(
            diropargs3(self.directory, self._name("shortlink")),
            symlinkdata3(unset_attributes(), b"abcdefgh")))
        self._expect_garbage_args("SYMLINK", payload[:-4])

    def test_truncated_symlink_target_is_raw_argument(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.symlink_truncated()
        tests._expect_garbage_args.assert_called_once()
        procedure, payload = tests._expect_garbage_args.call_args[0]
        assertions.assertEqual(procedure, "SYMLINK")
        assertions.assertIsInstance(payload, bytes)

    def test_symlink_dot_components_are_rejected(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests.call = Mock()
        tests.edge_symlink_dot_components()
        calls = tests._expect_status.call_args_list
        assertions.assertEqual(len(calls), 2)
        for call, component in zip(calls, (b".", b"..")):
            actual_procedure, args, actual_expected = call[0]
            assertions.assertEqual(actual_procedure, "SYMLINK")
            unpacker = NFS3Unpacker(tests._pack_args(args))
            decoded = getattr(
                unpacker, "unpack_" + args.__class__.__name__)()
            assertions.assertEqual(decoded.where.name, component)
            assertions.assertEqual(
                actual_expected, [NFS3ERR_EXIST, NFS3ERR_INVAL])
        assertions.assertEqual(tests._check_dot_namespace.call_count, 2)
