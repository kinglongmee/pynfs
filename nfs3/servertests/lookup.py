from .base import *
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import diropargs3
from xdrdef.nfs3_pack import NFS3Packer, NFS3Unpacker


class LookupTests:
    def test_lookup(self):
        if self._lookup(self.directory, self.file_name).data != self.file.data:
            raise AssertionError("LOOKUP returned a different file handle")


    def edge_lookup_noent(self):
        name = self._name("missing")
        self._expect_status("LOOKUP",
                            LOOKUP3args(diropargs3(self.directory, name)),
                            [NFS3ERR_NOENT])


    def edge_lookup_nametoolong(self):
        limits = self.call("PATHCONF", PATHCONF3args(self.directory))
        if limits.name_max > MAX_TEST_NAME_LENGTH:
            raise AssertionError("PATHCONF name_max exceeds safe test limit")
        name = b"x" * (limits.name_max + 1)
        self._expect_status("LOOKUP",
                            LOOKUP3args(diropargs3(self.directory, name)),
                            [NFS3ERR_NAMETOOLONG])


    def edge_lookup_dot_components(self):
        if self._lookup(self.directory, b".").data != self.directory.data:
            raise AssertionError("LOOKUP(.) did not return the same directory")
        parent = self._lookup(self.directory, b"..")
        if parent.data != self.root.data:
            raise AssertionError("LOOKUP(..) did not return the parent directory")


    def edge_lookup_special_names(self):
        names = (
            b"...", b"..hidden", b".leading", b"trailing.",
            b"name with spaces", b"semi;colon,comma",
            b"brackets[]{}()!$&'()+,;=@^_`~%",
            b"control-\x01",
        )
        for name in names:
            handle = self._create(name)
            if self._lookup(self.directory, name).data != handle.data:
                raise AssertionError("LOOKUP changed special filename %r" % name)

        renamed = b"..renamed !@#"
        source = names[0]
        source_handle = self._lookup(self.directory, source)
        self.call("RENAME", RENAME3args(
            diropargs3(self.directory, source),
            diropargs3(self.directory, renamed)))
        self.created_names.remove(source)
        self.created_names.append(renamed)
        if self._lookup(self.directory, renamed).data != source_handle.data:
            raise AssertionError("RENAME changed a special filename")

        result = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 8192))
        listed = {entry.name for entry in self._entries(result.reply.entries)}
        if (set(names[1:]) | {renamed}) - listed:
            raise AssertionError("READDIR omitted special filenames")


    def edge_lookup_non_utf8_name(self):
        name = b"raw-name-\xff-\xfe-\x80"
        handle = self._create(name)
        looked_up = self._lookup(self.directory, name)
        if looked_up.data != handle.data:
            raise AssertionError("LOOKUP changed a non-UTF-8 filename")
        entries = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 8192))
        names = {entry.name for entry in self._entries(entries.reply.entries)}
        if name not in names:
            raise AssertionError("READDIR omitted a non-UTF-8 filename")


    def invalid_names(self):
        for name in (b"", b"x" * 256, b"nul\0name", b"slash/name"):
            where = diropargs3(self.directory, name)
            valid = diropargs3(self.directory, self._name("decode"))
            cases = [
                ("LOOKUP", LOOKUP3args(where)),
                ("CREATE", CREATE3args(where, createhow3(
                    GUARDED, obj_attributes=unset_attributes()))),
                ("MKDIR", MKDIR3args(where, unset_attributes())),
                ("SYMLINK", SYMLINK3args(
                    where, symlinkdata3(unset_attributes(), LINK_DATA))),
                ("MKNOD", MKNOD3args(where, mknoddata3(
                    NF3FIFO, pipe_attributes=unset_attributes()))),
                ("REMOVE", REMOVE3args(where)),
                ("RMDIR", RMDIR3args(where)),
                ("RENAME", RENAME3args(where, valid)),
                ("RENAME", RENAME3args(valid, where)),
                ("LINK", LINK3args(self.file, where)),
            ]
            for procedure, args in cases:
                try:
                    self._expect_garbage_args(procedure, self._pack_args(args))
                except Exception as error:
                    raise AssertionError("%s name %r: %s" %
                                         (procedure, name, error)) from error

    def lookfile(self):
        if self._lookup(self.directory, self.file_name).data != self.file.data:
            raise AssertionError("LOOKUP returned a different file handle")

    def lookdir(self):
        attrs = self.call(
            "GETATTR", GETATTR3args(self.directory)).obj_attributes
        if attrs.type != NF3DIR:
            raise AssertionError(
                "Standard directory handle does not refer to a directory")

    def looklink(self):
        link = self._lookup(self.directory, b"seed-link")
        data = self.call("READLINK", READLINK3args(link)).data
        if data != LINK_DATA:
            raise AssertionError(
                "Standard symbolic-link handle has an unexpected target")

    def lookup_missing_entry(self):
        self._expect_status(
            "LOOKUP",
            LOOKUP3args(diropargs3(
                self.directory, self._name("lookup-missing"))),
            [NFS3ERR_NOENT])

    def lookup_non_directory(self):
        self._expect_status(
            "LOOKUP", LOOKUP3args(diropargs3(self.file, b"child")),
            [NFS3ERR_NOTDIR])

    def test_invalid_name_matrix_and_both_rename_operands(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.invalid_names()
        calls = tests._expect_garbage_args.call_args_list
        assert len(calls) == 40
        rename_names = []
        for call in calls:
            procedure, payload = call[0]
            assert isinstance(payload, bytes)
            if procedure == "RENAME":
                unpacker = NFS3Unpacker(payload)
                args = unpacker.unpack_RENAME3args()
                unpacker.done()
                rename_names.append((args.fromfile.name, args.tofile.name))
        invalid = (b"", b"x" * 256, b"nul\0name", b"slash/name")
        assert [pair[0] for pair in rename_names[::2]] == list(invalid)
        assert [pair[1] for pair in rename_names[1::2]] == list(invalid)

    def test_dot_and_special_filename_bytes_roundtrip(self):
        from . import NFS3Tests
        names = (
            b".", b"..", b"...", b"..hidden", b".leading", b"trailing.",
            b"name with spaces", b"semi;colon,comma",
            b"brackets[]{}()!$&'()+,;=@^_`~%", b"control-\x01", b"raw-\xff",
        )
        assert ("LOOKUP_SPECIAL_NAMES", "LOOKUP",
                "edge_lookup_special_names") in NFS3Tests.procedures
        for name in names:
            packer = NFS3Packer()
            packer.pack_LOOKUP3args(LOOKUP3args(
                diropargs3(nfs_fh3(b"directory"), name)))
            args = NFS3Unpacker(
                packer.get_buffer()).unpack_LOOKUP3args()
            assert args.what.name == name

    def test_dot_lookup_checks_both_components(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests.root = nfs_fh3(b"root")
        tests.directory = nfs_fh3(b"directory")
        tests._lookup = Mock(side_effect=[tests.directory, tests.root])
        tests.edge_lookup_dot_components()
        assert tests._lookup.call_count == 2

    def test_namespace_guard_detects_changed_directory_and_file(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests.root = nfs_fh3(b"root")
        tests.directory_name = b"private"
        tests.file_name = b"seed"
        tests.edge_lookup_dot_components = Mock()
        for handles in ((b"changed",), (b"directory", b"changed")):
            tests._lookup = Mock(
                side_effect=[nfs_fh3(handle) for handle in handles])
            try:
                tests._check_dot_namespace()
            except AssertionError as error:
                if "changed" not in str(error):
                    raise
            else:
                raise AssertionError(
                    "namespace guard did not detect a changed handle")
