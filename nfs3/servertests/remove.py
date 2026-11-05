from .base import *
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import *


class RemoveTests:
    def test_remove(self):
        name = b"remove-test"
        self._create(name)
        self._unlink(name)
        result = self.client.proc(NFSPROC3_LOOKUP, LOOKUP3args(
            diropargs3(self.directory, name)))
        if result.status != NFS3ERR_NOENT:
            raise AssertionError("REMOVE did not remove the file")


    def edge_remove_dot_components(self):
        self._expect_dot_status("REMOVE", REMOVE3args, [NFS3ERR_ACCES,NFS3ERR_INVAL])


    def edge_remove_errors(self):
        missing = self._name("remove-missing")
        self._expect_status("REMOVE",
                            REMOVE3args(diropargs3(self.directory, missing)),
                            [NFS3ERR_NOENT])
        name = self._name("remove-directory")
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        self._expect_status("REMOVE",
                            REMOVE3args(diropargs3(self.directory, name)),
                            [NFS3ERR_ISDIR, NFS3_OK])

    def remove_existing_file(self):
        name = self._name("remove-existing")
        self._create(name, mode=0o600)
        self._unlink(name)
        self._expect_status(
            "LOOKUP", LOOKUP3args(diropargs3(self.directory, name)),
            [NFS3ERR_NOENT])

    def remove_missing_entry(self):
        self._expect_status(
            "REMOVE",
            REMOVE3args(diropargs3(
                self.directory, self._name("remove-missing"))),
            [NFS3ERR_NOENT])

    def rmdir_empty_directory(self):
        name = self._name("remove-directory")
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o700)
        self.call("MKDIR", MKDIR3args(diropargs3(self.directory, name), attrs))
        self.created_names.append(name)
        try:
            self.call("RMDIR", RMDIR3args(diropargs3(self.directory, name)))
            self.created_names.remove(name)
            self._expect_status(
                "LOOKUP", LOOKUP3args(diropargs3(self.directory, name)),
                [NFS3ERR_NOENT])
        finally:
            if name in self.created_names:
                self.call("RMDIR", RMDIR3args(diropargs3(self.directory, name)))
                self.created_names.remove(name)

    def test_remove_dot_components_are_rejected(self):
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
        tests.edge_remove_dot_components()
        calls = tests._expect_status.call_args_list
        assertions.assertEqual(len(calls), 2)
        for call, component in zip(calls, (b".", b"..")):
            actual_procedure, args, actual_expected = call[0]
            assertions.assertEqual(actual_procedure, "REMOVE")
            unpacker = NFS3Unpacker(tests._pack_args(args))
            decoded = getattr(
                unpacker, "unpack_" + args.__class__.__name__)()
            assertions.assertEqual(decoded.object.name, component)
            assertions.assertEqual(
                actual_expected, [NFS3ERR_ACCES, NFS3ERR_INVAL])
        assertions.assertEqual(tests._check_dot_namespace.call_count, 2)
