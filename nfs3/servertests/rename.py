from .base import *
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import diropargs3


class RenameTests:
    def test_rename(self):
        source, target = b"rename-source", b"rename-target"
        self._create(source)
        args = RENAME3args(diropargs3(self.directory, source),
                           diropargs3(self.directory, target))
        self.call("RENAME", args)
        self.created_names.remove(source)
        self.created_names.append(target)
        if self._lookup(self.directory, target).data == b"":
            raise AssertionError("RENAME returned an empty file handle")


    def edge_rename_dot_components(self):
        name = self._name("dot-rename-source")
        handle = self._create(name)
        ordinary = diropargs3(self.directory, name)
        for component in (b".", b".."):
            special = diropargs3(self.directory, component)
            for source, target in ((special, ordinary), (ordinary, special)):
                self._expect_status(
                    "RENAME", RENAME3args(source, target), [NFS3ERR_PERM,NFS3ERR_INVAL])
                self._check_dot_namespace()
                if self._lookup(self.directory, name).data != handle.data:
                    raise AssertionError("rejected RENAME changed its source")
            for target_component in (b".", b".."):
                self._expect_status(
                    "RENAME", RENAME3args(special, diropargs3(
                        self.directory, target_component)), [NFS3ERR_PERM,NFS3ERR_INVAL])
                self._check_dot_namespace()


    def edge_rename_replace(self):
        source, target = self._name("from"), self._name("to")
        source_fh = self._create(source)
        self._create(target)
        args = RENAME3args(diropargs3(self.directory, source),
                           diropargs3(self.directory, target))
        self.call("RENAME", args)
        self.created_names.remove(source)
        if self._lookup(self.directory, target).data != source_fh.data:
            raise AssertionError("RENAME did not replace the target")


    def edge_rename_same(self):
        name = self._name("same")
        handle = self._create(name)
        self.call("RENAME", RENAME3args(
            diropargs3(self.directory, name),
            diropargs3(self.directory, name)))
        if self._lookup(self.directory, name).data != handle.data:
            raise AssertionError("same-name RENAME changed the file")

    def rename_preserves_file_handle(self):
        source = self._name("rename-source")
        target = self._name("rename-target")
        handle = self._create(source, mode=0o600)
        try:
            self.call("RENAME", RENAME3args(
                diropargs3(self.directory, source),
                diropargs3(self.directory, target)))
            self.created_names.remove(source)
            self.created_names.append(target)
            if self._lookup(self.directory, target).data != handle.data:
                raise AssertionError("RENAME changed the file handle")
            self._expect_status(
                "LOOKUP", LOOKUP3args(diropargs3(self.directory, source)),
                [NFS3ERR_NOENT])
        finally:
            for name in (source, target):
                if name in self.created_names:
                    self._unlink(name)

    def rename_missing_source(self):
        self._expect_status(
            "RENAME", RENAME3args(
                diropargs3(self.directory, self._name("rename-missing")),
                diropargs3(self.directory, self._name("rename-target"))),
            [NFS3ERR_NOENT])

    def test_dot_cases_cover_both_operands(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests._create = Mock(return_value=nfs_fh3(b"source"))
        tests._lookup = Mock(return_value=nfs_fh3(b"source"))
        tests.edge_rename_dot_components()
        calls = tests._expect_status.call_args_list
        pairs = [(call[0][1].fromfile.name, call[0][1].tofile.name)
                 for call in calls]
        ordinary = tests._create.call_args[0][0]
        assertions.assertEqual(set(pairs), {
            (b".", ordinary), (ordinary, b"."),
            (b"..", ordinary), (ordinary, b".."),
            (b".", b"."), (b".", b".."),
            (b"..", b"."), (b"..", b".."),
        })
        assertions.assertEqual(len(calls), 8)
        for call in calls:
            assertions.assertEqual(
                call[0][2], [NFS3ERR_PERM, NFS3ERR_INVAL])
        assertions.assertEqual(tests._check_dot_namespace.call_count, 8)

    def test_rename_detects_changed_source(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests._create = Mock(return_value=nfs_fh3(b"source"))
        tests._lookup = Mock(return_value=nfs_fh3(b"changed"))
        with assertions.assertRaisesRegex(AssertionError, "changed its source"):
            tests.edge_rename_dot_components()
