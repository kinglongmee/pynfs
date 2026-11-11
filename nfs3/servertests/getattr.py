from .base import *
from xdrdef.nfs3_const import *


class GetattrTests:
    def test_getattr(self):
        attrs = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if attrs.type != NF3REG or attrs.size != len(TEST_DATA):
            raise AssertionError("GETATTR returned unexpected file attributes")


    def edge_getattr_symlink(self):
        link = self._lookup(self.directory, b"seed-link")
        attrs = self.call("GETATTR", GETATTR3args(link)).obj_attributes
        if attrs.type != NF3LNK or attrs.size != len(LINK_DATA):
            raise AssertionError("GETATTR returned unexpected symlink attributes")


    def edge_getattr_object_attributes(self):
        handles = (
            (self.root, NF3DIR, None),
            (self.directory, NF3DIR, None),
            (self.file, NF3REG, len(TEST_DATA)),
            (self._lookup(self.directory, b"seed-link"),
             NF3LNK, len(LINK_DATA)),
        )
        observed = []
        for handle, expected_type, expected_size in handles:
            first = self.call(
                "GETATTR", GETATTR3args(handle)).obj_attributes
            second = self.call(
                "GETATTR", GETATTR3args(handle)).obj_attributes
            if first.type != expected_type:
                raise AssertionError("GETATTR returned the wrong object type")
            if expected_size is not None and first.size != expected_size:
                raise AssertionError("GETATTR returned the wrong object size")
            if first.nlink == 0:
                raise AssertionError("GETATTR returned a zero link count")
            if first.mode & ~0o7777:
                raise AssertionError("GETATTR returned invalid permission bits")
            for timestamp in (first.atime, first.mtime, first.ctime):
                if timestamp.nseconds >= 1000000000:
                    raise AssertionError(
                        "GETATTR returned out-of-range timestamp nanoseconds")
            if (first.fileid, first.fsid, first.type) != \
                    (second.fileid, second.fsid, second.type):
                raise AssertionError(
                    "GETATTR returned unstable object identity attributes")
            observed.append(first)

        fsids = {attrs.fsid for attrs in observed}
        if len(fsids) != 1:
            raise AssertionError("objects in the test export have different fsids")
        fileids = [attrs.fileid for attrs in observed]
        if len(fileids) != len(set(fileids)):
            raise AssertionError("distinct test objects share a fileid")


    def edge_getattr_stale_handle(self):
        name = self._name("getattr-stale")
        handle = self._create(name)
        self._unlink(name)
        self._expect_status(
            "GETATTR", GETATTR3args(handle), [NFS3ERR_STALE])


    def edge_getattr_empty_handle(self):
        self._expect_status(
            "GETATTR", GETATTR3args(nfs_fh3(b"")),
            [NFS3ERR_BADHANDLE, NFS3ERR_STALE])


    def handle_length(self):
        for size in (0, NFS3_FHSIZE + 1):
            packer = NFS3Packer()
            packer.pack_opaque(b"x" * size)
            self._expect_garbage_args("GETATTR", packer.get_buffer())


    def handle_truncated(self):
        self._expect_garbage_args("GETATTR", struct.pack(">I", 8) + b"abcd")

    def getattr_file_attributes(self):
        attrs = self.call(
            "GETATTR", GETATTR3args(self.file)).obj_attributes
        for field in ("type", "mode", "nlink", "uid", "gid", "size",
                      "used", "rdev", "fsid", "fileid", "atime", "mtime",
                      "ctime"):
            if not hasattr(attrs, field):
                raise AssertionError(
                    "GETATTR did not return required attribute %s" % field)

    def getattr_directory_attributes(self):
        attrs = self.call(
            "GETATTR", GETATTR3args(self.directory)).obj_attributes
        if attrs.type != NF3DIR:
            raise AssertionError(
                "GETATTR returned type %s for directory" % attrs.type)

    def test_handle_lengths_and_truncation_bypass_client_packer(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.handle_length()
        payloads = [call[0][1] for call in
                    tests._expect_garbage_args.call_args_list]
        assert [struct.unpack(">I", p[:4])[0] for p in payloads] == [0, 65]
        tests._expect_garbage_args.reset_mock()
        tests.handle_truncated()
        payload = tests._expect_garbage_args.call_args[0][1]
        assert payload == struct.pack(">I", 8) + b"abcd"

    def test_only_garbage_args_rpc_error_is_accepted(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        pipe = tests.client.get_pipe.return_value
        error = rpc.RPCAcceptError.__new__(rpc.RPCAcceptError)
        error.stat = rpc.GARBAGE_ARGS
        pipe.listen.side_effect = error
        tests._expect_garbage_args("GETATTR", b"")
        error.stat = rpc.SYSTEM_ERR
        try:
            tests._expect_garbage_args("GETATTR", b"")
        except rpc.RPCAcceptError:
            pass
        else:
            raise AssertionError("non-GARBAGE_ARGS reply was accepted")

    def test_success_and_timeouts_do_not_pass(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        pipe = tests.client.get_pipe.return_value
        try:
            tests._expect_garbage_args("GETATTR", b"")
        except AssertionError as error:
            if "accepted malformed" not in str(error):
                raise
        else:
            raise AssertionError("malformed arguments were accepted")
        pipe.listen.side_effect = rpc.RPCTimeout()
        try:
            tests._expect_garbage_args("GETATTR", b"")
        except rpc.RPCTimeout:
            pass
        else:
            raise AssertionError("RPC timeout was not propagated")
