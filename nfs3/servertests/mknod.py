from .base import *


class MknodTests:
    def test_mknod(self):
        name = b"mknod-test"
        args = MKNOD3args(
            diropargs3(self.directory, name),
            mknoddata3(NF3FIFO, pipe_attributes=unset_attributes()))
        self.call("MKNOD", args)
        self.created_names.append(name)
        handle = self._lookup(self.directory, name)
        if self.call("GETATTR", GETATTR3args(handle)).obj_attributes.type != NF3FIFO:
            raise AssertionError("MKNOD did not create a FIFO")


    def edge_mknod_dot_components(self):
        self._expect_dot_status(
            "MKNOD", lambda where: MKNOD3args(
                where, mknoddata3(NF3FIFO, pipe_attributes=unset_attributes())),
            [NFS3ERR_EXIST,NFS3ERR_INVAL])


    def edge_mknod_socket(self):
        self._optional_mknod(
            self._name("socket"), NF3SOCK,
            mknoddata3(NF3SOCK, pipe_attributes=unset_attributes()))


    def edge_mknod_char(self):
        self._optional_mknod(
            self._name("char"), NF3CHR,
            mknoddata3(NF3CHR, device=devicedata3(
                unset_attributes(), specdata3(1, 7))))


    def edge_mknod_block(self):
        self._optional_mknod(
            self._name("block"), NF3BLK,
            mknoddata3(NF3BLK, device=devicedata3(
                unset_attributes(), specdata3(1, 7))))


    def mknod_type(self):
        prefix = self._pack_args(LOOKUP3args(diropargs3(
            self.directory, self._name("badtype"))))
        for kind in (0, 8, 0xffffffff):
            self._expect_garbage_args(
                "MKNOD", prefix + struct.pack(">I", kind))


    def mknod_badtype(self):
        for kind in (NF3REG, NF3DIR, NF3LNK):
            self._expect_status("MKNOD", MKNOD3args(
                diropargs3(self.directory, self._name("illegaltype")),
                mknoddata3(kind)), [NFS3ERR_BADTYPE])

    def test_invalid_mknod_types_are_raw_arguments(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.mknod_type()
        calls = tests._expect_garbage_args.call_args_list
        assert len(calls) == 3
        assert all(
            call[0][0] == "MKNOD" and isinstance(call[0][1], bytes)
            for call in calls)

    def test_mknod_dot_components_are_rejected(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests.call = Mock()
        tests.edge_mknod_dot_components()
        calls = tests._expect_status.call_args_list
        assert len(calls) == 2
        for call, component in zip(calls, (b".", b"..")):
            actual_procedure, args, actual_expected = call[0]
            assert actual_procedure == "MKNOD"
            unpacker = NFS3Unpacker(tests._pack_args(args))
            decoded = getattr(
                unpacker, "unpack_" + args.__class__.__name__)()
            assert decoded.where.name == component
            assert actual_expected == [NFS3ERR_EXIST, NFS3ERR_INVAL]
        assert tests._check_dot_namespace.call_count == 2
