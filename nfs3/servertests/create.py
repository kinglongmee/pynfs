from .base import *
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import *


class CreateTests:
    def test_create(self):
        handle = self._create(b"create-test")
        attrs = self.call("GETATTR", GETATTR3args(handle)).obj_attributes
        if attrs.type != NF3REG:
            raise AssertionError("CREATE did not create a regular file")


    def edge_create_dot_components(self):
        for mode in (UNCHECKED, GUARDED, EXCLUSIVE):
            def make_args(where):
                how = (createhow3(EXCLUSIVE, verf=b"dot-verf")
                       if mode == EXCLUSIVE else
                       createhow3(mode, obj_attributes=unset_attributes()))
                return CREATE3args(where, how)
            self._expect_dot_status("CREATE", make_args, [NFS3ERR_EXIST,NFS3ERR_INVAL])


    def edge_create_modes(self):
        guarded_name = self._name("guarded")
        self._create(guarded_name)
        guarded = CREATE3args(
            diropargs3(self.directory, guarded_name),
            createhow3(GUARDED, obj_attributes=unset_attributes()))
        self._expect_status("CREATE", guarded, [NFS3ERR_EXIST])

        unchecked = CREATE3args(
            diropargs3(self.directory, guarded_name),
            createhow3(UNCHECKED, obj_attributes=unset_attributes()))
        self.call("CREATE", unchecked)

        exclusive_name = self._name("exclusive")
        verifier = b"pynfs3v1"
        exclusive = CREATE3args(
            diropargs3(self.directory, exclusive_name),
            createhow3(EXCLUSIVE, verf=verifier))
        self.call("CREATE", exclusive)
        self.created_names.append(exclusive_name)
        self.call("CREATE", exclusive)
        different_verifier = CREATE3args(
            diropargs3(self.directory, exclusive_name),
            createhow3(EXCLUSIVE, verf=b"pynfs3v2"))
        self._expect_status("CREATE", different_verifier, [NFS3ERR_EXIST])


    def edge_create_empty_name(self):
        args = CREATE3args(
            diropargs3(self.directory, b""),
            createhow3(GUARDED, obj_attributes=unset_attributes()))
        self._expect_status("CREATE", args, [NFS3ERR_INVAL])


    def create_mode(self):
        prefix = self._pack_args(LOOKUP3args(diropargs3(
            self.directory, self._name("badmode"))))
        for mode in (3, 0xffffffff):
            self._expect_garbage_args(
                "CREATE", prefix + struct.pack(">I", mode))


    def create_verifier(self):
        payload = self._pack_args(CREATE3args(
            diropargs3(self.directory, self._name("shortverf")),
            createhow3(EXCLUSIVE, verf=b"12345678")))
        for length in (4, 8):
            self._expect_garbage_args("CREATE", payload[:-length])

    def create_guarded_existing(self):
        name = self._name("create-guarded")
        self._create(name, mode=0o600)
        args = CREATE3args(diropargs3(self.directory, name),
                           createhow3(
                               GUARDED, obj_attributes=unset_attributes()))
        try:
            self._expect_status("CREATE", args, [NFS3ERR_EXIST])
        finally:
            self._unlink(name)

    def mkdir_create_directory(self):
        name = self._name("mkdir-create")
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o700)
        self.call("MKDIR", MKDIR3args(diropargs3(self.directory, name), attrs))
        self.created_names.append(name)
        try:
            handle = self._lookup(self.directory, name)
            attrs = self.call("GETATTR", GETATTR3args(handle)).obj_attributes
            if attrs.type != NF3DIR:
                raise AssertionError("MKDIR did not create a directory")
        finally:
            self.call("RMDIR", RMDIR3args(diropargs3(self.directory, name)))
            self.created_names.remove(name)

    def symlink_create_target(self):
        name = self._name("symlink-create")
        target = b"/nfs3-test-target"
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o777)
        args = SYMLINK3args(
            diropargs3(self.directory, name),
            symlinkdata3(attrs, target))
        self.call("SYMLINK", args)
        self.created_names.append(name)
        try:
            handle = self._lookup(self.directory, name)
            if self.call("READLINK", READLINK3args(handle)).data != target:
                raise AssertionError("SYMLINK target did not round-trip")
        finally:
            self._unlink(name)

    def mkfifo(self):
        self._test_mknod(NF3FIFO, "fifo")

    def mksock(self):
        self._test_mknod(NF3SOCK, "socket")

    def mkchar(self):
        self._test_mknod(NF3CHR, "char")

    def mkblk(self):
        self._test_mknod(NF3BLK, "block")

    def _test_mknod(self, filetype, prefix):
        name = self._name(prefix)
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o600)
        if filetype in (NF3BLK, NF3CHR):
            data = mknoddata3(
                filetype, device=devicedata3(attrs, specdata3(0, 0)))
        else:
            data = mknoddata3(filetype, pipe_attributes=attrs)
        args = MKNOD3args(diropargs3(self.directory, name), data)
        result = self.client.proc(NFSPROC3_MKNOD, args)
        if result.status in (NFS3ERR_PERM, NFS3ERR_NOTSUPP):
            raise NFS3TestUnsupported(
                "MKNOD of %s is not available" % name.decode("ascii"))
        if result.status != NFS3_OK:
            self._expect_status("MKNOD", args, [NFS3_OK])
        self.created_names.append(name)
        try:
            handle = self._lookup(self.directory, name)
            actual_type = self.call(
                "GETATTR", GETATTR3args(handle)).obj_attributes.type
            if actual_type != filetype:
                raise AssertionError(
                    "MKNOD created type %d, expected %d" %
                    (actual_type, filetype))
        finally:
            self._unlink(name)

    def test_invalid_create_modes_are_raw_arguments(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.create_mode()
        calls = tests._expect_garbage_args.call_args_list
        assertions.assertEqual(len(calls), 2)
        assertions.assertTrue(all(
            call[0][0] == "CREATE" and isinstance(call[0][1], bytes)
            for call in calls))

    def test_short_create_verifiers_are_raw_arguments(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.create_verifier()
        calls = tests._expect_garbage_args.call_args_list
        assertions.assertEqual(len(calls), 2)
        assertions.assertTrue(all(
            call[0][0] == "CREATE" and isinstance(call[0][1], bytes)
            for call in calls))

    def test_create_dot_cases_cover_all_modes(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests.edge_create_dot_components()
        calls = tests._expect_status.call_args_list
        assertions.assertEqual(len(calls), 6)
        assertions.assertEqual(
            [(call[0][1].where.name, call[0][1].how.mode) for call in calls],
            [(component, mode) for mode in (UNCHECKED, GUARDED, EXCLUSIVE)
             for component in (b".", b"..")])
