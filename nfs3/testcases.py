"""NFSv3 procedure tests based on RFC 1813."""

import os

import use_local
import rpc.rpc as rpc
from nfs3client import NFS3Client
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import *


TEST_DATA = b"pynfs NFSv3 RFC 1813 test data"
LINK_DATA = b"nfs3-link-target"
NULL_VERIFIER = b"\0" * NFS3_COOKIEVERFSIZE
MAX_TEST_NAME_LENGTH = 1024 * 1024


def unset_attributes():
    return sattr3(
        set_mode3(FALSE), set_uid3(FALSE), set_gid3(FALSE), set_size3(FALSE),
        set_atime(DONT_CHANGE), set_mtime(DONT_CHANGE))


class NFS3Tests:
    procedures = [
        ("NULL", "test_null"),
        ("GETATTR", "test_getattr"),
        ("SETATTR", "test_setattr"),
        ("LOOKUP", "test_lookup"),
        ("ACCESS", "test_access"),
        ("READLINK", "test_readlink"),
        ("READ", "test_read"),
        ("WRITE", "test_write"),
        ("CREATE", "test_create"),
        ("MKDIR", "test_mkdir"),
        ("SYMLINK", "test_symlink"),
        ("MKNOD", "test_mknod"),
        ("REMOVE", "test_remove"),
        ("RMDIR", "test_rmdir"),
        ("RENAME", "test_rename"),
        ("LINK", "test_link"),
        ("READDIR", "test_readdir"),
        ("READDIRPLUS", "test_readdirplus"),
        ("FSSTAT", "test_fsstat"),
        ("FSINFO", "test_fsinfo"),
        ("PATHCONF", "test_pathconf"),
        ("COMMIT", "test_commit"),
    ]
    edge_cases = [
        ("GETATTR_SYMLINK", "GETATTR", "edge_getattr_symlink"),
        ("SETATTR_SIZE_ZERO", "SETATTR", "edge_setattr_size_zero"),
        ("SETATTR_GUARD", "SETATTR", "edge_setattr_guard"),
        ("LOOKUP_NOENT", "LOOKUP", "edge_lookup_noent"),
        ("LOOKUP_NAMETOOLONG", "LOOKUP", "edge_lookup_nametoolong"),
        ("LOOKUP_DOT_COMPONENTS", "LOOKUP", "edge_lookup_dot_components"),
        ("ACCESS_MASK", "ACCESS", "edge_access_mask"),
        ("ACCESS_UNKNOWN_BITS", "ACCESS", "edge_access_unknown_bits"),
        ("READLINK_WRONG_TYPE", "READLINK", "edge_readlink_wrong_type"),
        ("READLINK_LONG_TARGET", "READLINK", "edge_readlink_long_target"),
        ("READ_ZERO_COUNT", "READ", "edge_read_zero_count"),
        ("READ_BEYOND_EOF", "READ", "edge_read_beyond_eof"),
        ("READ_MAX_COUNT", "READ", "edge_read_max_count"),
        ("WRITE_STABILITY", "WRITE", "edge_write_stability"),
        ("WRITE_ZERO_COUNT", "WRITE", "edge_write_zero_count"),
        ("WRITE_SPARSE_OFFSET", "WRITE", "edge_write_sparse_offset"),
        ("WRITE_OFFSET_OVERFLOW", "WRITE", "edge_write_offset_overflow"),
        ("CREATE_MODES", "CREATE", "edge_create_modes"),
        ("CREATE_EMPTY_NAME", "CREATE", "edge_create_empty_name"),
        ("MKDIR_EXIST", "MKDIR", "edge_mkdir_exist"),
        ("SYMLINK_EXIST", "SYMLINK", "edge_symlink_exist"),
        ("MKNOD_SOCKET", "MKNOD", "edge_mknod_socket"),
        ("MKNOD_CHAR", "MKNOD", "edge_mknod_char"),
        ("MKNOD_BLOCK", "MKNOD", "edge_mknod_block"),
        ("REMOVE_ERRORS", "REMOVE", "edge_remove_errors"),
        ("RMDIR_NOTEMPTY", "RMDIR", "edge_rmdir_notempty"),
        ("RENAME_REPLACE", "RENAME", "edge_rename_replace"),
        ("RENAME_SAME", "RENAME", "edge_rename_same"),
        ("LINK_DIRECTORY", "LINK", "edge_link_directory"),
        ("READDIR_COOKIES", "READDIR", "edge_readdir_cookies"),
        ("READDIR_BAD_COOKIE", "READDIR", "edge_readdir_bad_cookie"),
        ("READDIR_BAD_VERIFIER", "READDIR", "edge_readdir_bad_verifier"),
        ("READDIRPLUS_TOOSMALL", "READDIRPLUS", "edge_readdirplus_toosmall"),
        ("FSSTAT_COUNTS", "FSSTAT", "edge_fsstat_counts"),
        ("FSINFO_LIMITS", "FSINFO", "edge_fsinfo_limits"),
        ("PATHCONF_NAME_MAX", "PATHCONF", "edge_pathconf_name_max"),
        ("COMMIT_RANGE", "COMMIT", "edge_commit_range"),
    ]

    def __init__(self, server, export, port=None, uid=None, gid=None):
        self.client = NFS3Client(server, port=port)
        uid = os.getuid() if uid is None else uid
        gid = os.getgid() if gid is None else gid
        self.cred = rpc.security.instance(rpc.AUTH_SYS).init_cred(
            uid=uid, gid=gid, name=os.fsencode(os.uname().nodename))
        self.client.set_cred(self.cred)
        self.client.mntclnt.default_cred = self.cred
        root_handle = self.client.mntclnt.get_rootfh([export.lstrip("/")])
        if not root_handle:
            raise RuntimeError("MOUNT did not return an NFSv3 file handle")
        self.root = nfs_fh3(root_handle)

        suffix = os.urandom(4).hex()
        self.directory_name = ("pynfs3-%d-%s" %
                               (os.getpid(), suffix)).encode("ascii")
        self.directory = None
        self.file_name = b"seed"
        self.file = None
        self.created_names = []
        self._serial = 0
        self._mkdir(self.root, self.directory_name)
        self.directory = self._lookup(self.root, self.directory_name)
        self.file = self._create(self.file_name)
        write = self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))
        if write.count != len(TEST_DATA):
            raise RuntimeError("Could not initialize NFSv3 test file")
        self._symlink(b"seed-link")
        self.failures = []

    def call(self, procedure, args):
        procnum = globals()["NFSPROC3_" + procedure]
        result = self.client.proc(procnum, args)
        if result.status != NFS3_OK:
            status_name = nfsstat3.get(result.status, str(result.status))
            raise AssertionError("%s returned %s" % (procedure, status_name))
        return result.resok

    def _create(self, name, parent=None):
        attrs = unset_attributes()
        how = createhow3(GUARDED, obj_attributes=attrs)
        result = self.call("CREATE", CREATE3args(
            diropargs3(parent or self.directory, name), how))
        if not result.obj.handle_follows:
            raise AssertionError("CREATE succeeded without returning a handle")
        self.created_names.append(name)
        return result.obj.handle

    def _mkdir(self, parent, name):
        attrs = unset_attributes()
        self.call("MKDIR", MKDIR3args(diropargs3(parent, name), attrs))

    def _lookup(self, parent, name):
        return self.call("LOOKUP", LOOKUP3args(
            diropargs3(parent, name))).object

    def _symlink(self, name):
        args = SYMLINK3args(
            diropargs3(self.directory, name),
            symlinkdata3(unset_attributes(), LINK_DATA))
        result = self.call("SYMLINK", args)
        self.created_names.append(name)
        return result

    def _unlink(self, name):
        self.call("REMOVE", REMOVE3args(diropargs3(self.directory, name)))
        if name in self.created_names:
            self.created_names.remove(name)

    def _name(self, prefix):
        self._serial += 1
        return ("%s-%d" % (prefix, self._serial)).encode("ascii")

    def _expect_status(self, procedure, args, expected):
        result = self.client.proc(globals()["NFSPROC3_" + procedure], args)
        if result.status not in expected:
            actual = nfsstat3.get(result.status, str(result.status))
            names = [nfsstat3.get(status, str(status)) for status in expected]
            raise AssertionError("%s returned %s, expected %s" %
                                 (procedure, actual, " or ".join(names)))
        return result

    def _optional_mknod(self, name, kind, what):
        result = self.client.proc(NFSPROC3_MKNOD, MKNOD3args(
            diropargs3(self.directory, name), what))
        if result.status == NFS3_OK:
            self.created_names.append(name)
            actual_type = self.call(
                "GETATTR", GETATTR3args(self._lookup(self.directory, name))
            ).obj_attributes.type
            if actual_type != kind:
                raise AssertionError("MKNOD created type %s, expected %s" %
                                     (ftype3.get(actual_type, actual_type),
                                      ftype3[kind]))
        elif result.status not in (NFS3ERR_PERM, NFS3ERR_ACCES,
                                  NFS3ERR_NODEV, NFS3ERR_NOTSUPP,
                                  NFS3ERR_BADTYPE, NFS3ERR_ROFS,
                                  NFS3ERR_NOSPC):
            raise AssertionError("MKNOD returned unexpected status %s" %
                                 nfsstat3.get(result.status, result.status))

    def test_null(self):
        self.client.null()

    def test_getattr(self):
        attrs = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if attrs.type != NF3REG or attrs.size != len(TEST_DATA):
            raise AssertionError("GETATTR returned unexpected file attributes")

    def test_setattr(self):
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o600)
        self.call("SETATTR", SETATTR3args(
            self.file, attrs, sattrguard3(FALSE)))
        result = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if result.mode & 0o777 != 0o600:
            raise AssertionError("SETATTR did not update the file mode")

    def test_lookup(self):
        if self._lookup(self.directory, self.file_name).data != self.file.data:
            raise AssertionError("LOOKUP returned a different file handle")

    def test_access(self):
        requested = ACCESS3_READ
        granted = self.call("ACCESS", ACCESS3args(self.file, requested)).access
        if granted & requested != requested:
            raise AssertionError("ACCESS did not grant READ on the test file")
        if granted & ~requested:
            raise AssertionError("ACCESS returned unrequested access bits")

    def test_readlink(self):
        link = self._lookup(self.directory, b"seed-link")
        data = self.call("READLINK", READLINK3args(link)).data
        if data != LINK_DATA:
            raise AssertionError("READLINK returned %r" % data)

    def test_read(self):
        result = self.call("READ", READ3args(self.file, 0, len(TEST_DATA)))
        if result.count != len(TEST_DATA) or result.data != TEST_DATA or \
                not result.eof:
            raise AssertionError("READ returned incomplete or unexpected data")

    def test_write(self):
        result = self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))
        if result.count != len(TEST_DATA) or result.committed != FILE_SYNC:
            raise AssertionError("WRITE returned an unexpected count or stability")

    def test_create(self):
        handle = self._create(b"create-test")
        attrs = self.call("GETATTR", GETATTR3args(handle)).obj_attributes
        if attrs.type != NF3REG:
            raise AssertionError("CREATE did not create a regular file")

    def test_mkdir(self):
        name = b"mkdir-test"
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        if self.call("GETATTR", GETATTR3args(
                self._lookup(self.directory, name))).obj_attributes.type != NF3DIR:
            raise AssertionError("MKDIR did not create a directory")

    def test_symlink(self):
        self._symlink(b"symlink-test")
        link = self._lookup(self.directory, b"symlink-test")
        if self.call("GETATTR", GETATTR3args(link)).obj_attributes.type != NF3LNK:
            raise AssertionError("SYMLINK did not create a symbolic link")

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

    def test_remove(self):
        name = b"remove-test"
        self._create(name)
        self._unlink(name)
        result = self.client.proc(NFSPROC3_LOOKUP, LOOKUP3args(
            diropargs3(self.directory, name)))
        if result.status != NFS3ERR_NOENT:
            raise AssertionError("REMOVE did not remove the file")

    def test_rmdir(self):
        name = b"rmdir-test"
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        self.call("RMDIR", RMDIR3args(diropargs3(self.directory, name)))
        self.created_names.remove(name)

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

    def test_link(self):
        name = b"link-test"
        result = self.call("LINK", LINK3args(
            self.file, diropargs3(self.directory, name)))
        self.created_names.append(name)
        attrs = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if attrs.nlink < 2:
            raise AssertionError("LINK did not increase the link count")
        if result.file_attributes.attributes_follow and \
                result.file_attributes.attributes.fileid != attrs.fileid:
            raise AssertionError("LINK returned attributes for another file")

    @staticmethod
    def _entries(head):
        while head:
            if isinstance(head, list):
                if not head:
                    return
                head = head[0]
            yield head
            head = head.nextentry

    def test_readdir(self):
        result = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 8192))
        names = {entry.name for entry in self._entries(result.reply.entries)}
        if self.file_name not in names:
            raise AssertionError("READDIR omitted the seed file")

    def test_readdirplus(self):
        result = self.call("READDIRPLUS", READDIRPLUS3args(
            self.directory, 0, NULL_VERIFIER, 8192, 16384))
        entries = list(self._entries(result.reply.entries))
        entry = next((e for e in entries if e.name == self.file_name), None)
        if entry is None:
            raise AssertionError("READDIRPLUS omitted the seed file")
        if entry.name_handle.handle_follows and \
                entry.name_handle.handle.data != self.file.data:
            raise AssertionError("READDIRPLUS returned the wrong file handle")
        if entry.name_attributes.attributes_follow and \
                entry.name_attributes.attributes.type != NF3REG:
            raise AssertionError("READDIRPLUS returned the wrong file attributes")

    def test_fsstat(self):
        result = self.call("FSSTAT", FSSTAT3args(self.root))
        if result.tbytes < result.fbytes or result.tfiles < result.ffiles:
            raise AssertionError("FSSTAT returned inconsistent totals")

    def test_fsinfo(self):
        result = self.call("FSINFO", FSINFO3args(self.root))
        if min(result.rtmax, result.rtpref, result.rtmult,
               result.wtmax, result.wtpref, result.wtmult,
               result.dtpref, result.maxfilesize) <= 0:
            raise AssertionError("FSINFO returned a non-positive limit")
        if result.time_delta.nseconds >= 1000000000:
            raise AssertionError("FSINFO returned an invalid time_delta")

    def test_pathconf(self):
        result = self.call("PATHCONF", PATHCONF3args(self.directory))
        if result.linkmax < 1 or result.name_max < 1:
            raise AssertionError("PATHCONF returned an invalid limit")

    def test_commit(self):
        write = self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), UNSTABLE, TEST_DATA))
        commit = self.call("COMMIT", COMMIT3args(self.file, 0, 0))
        if write.verf != commit.verf:
            raise AssertionError("COMMIT write verifier differs from WRITE")

    def edge_getattr_symlink(self):
        link = self._lookup(self.directory, b"seed-link")
        attrs = self.call("GETATTR", GETATTR3args(link)).obj_attributes
        if attrs.type != NF3LNK or attrs.size != len(LINK_DATA):
            raise AssertionError("GETATTR returned unexpected symlink attributes")

    def edge_setattr_size_zero(self):
        attrs = unset_attributes()
        attrs.size = set_size3(TRUE, 0)
        self.call("SETATTR", SETATTR3args(
            self.file, attrs, sattrguard3(FALSE)))
        result = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if result.size != 0:
            raise AssertionError("SETATTR did not truncate the file to zero")
        self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))

    def edge_setattr_guard(self):
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o600)
        result = self._expect_status(
            "SETATTR",
            SETATTR3args(self.file, attrs,
                         sattrguard3(TRUE, nfstime3(0, 0))),
            [NFS3ERR_NOT_SYNC])
        del result

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
        if parent.data == self.directory.data:
            raise AssertionError("LOOKUP(..) returned the child directory")

    def edge_access_mask(self):
        requested = (ACCESS3_READ | ACCESS3_LOOKUP | ACCESS3_MODIFY |
                     ACCESS3_EXTEND | ACCESS3_DELETE | ACCESS3_EXECUTE)
        result = self.call("ACCESS", ACCESS3args(self.file, requested))
        if result.access & ~requested:
            raise AssertionError("ACCESS returned unrequested access bits")
        if not result.access & ACCESS3_READ:
            raise AssertionError("ACCESS did not grant READ on the seed file")

    def edge_access_unknown_bits(self):
        requested = 0xffffffff
        result = self.call("ACCESS", ACCESS3args(self.file, requested))
        valid = (ACCESS3_READ | ACCESS3_LOOKUP | ACCESS3_MODIFY |
                 ACCESS3_EXTEND | ACCESS3_DELETE | ACCESS3_EXECUTE)
        if result.access & ~valid:
            raise AssertionError("ACCESS returned undefined access bits")

    def edge_readlink_wrong_type(self):
        self._expect_status("READLINK", READLINK3args(self.file),
                            [NFS3ERR_INVAL, NFS3ERR_NOTSUPP])

    def edge_readlink_long_target(self):
        name = self._name("longlink")
        target = b"/" + b"target/" * 64
        result = self.call("SYMLINK", SYMLINK3args(
            diropargs3(self.directory, name),
            symlinkdata3(unset_attributes(), target)))
        self.created_names.append(name)
        handle = self._lookup(self.directory, name)
        returned = self.call("READLINK", READLINK3args(handle)).data
        if returned != target:
            raise AssertionError("READLINK corrupted a long target")
        del result

    def edge_read_zero_count(self):
        result = self.call("READ", READ3args(self.file, 0, 0))
        if result.count != 0 or result.data:
            raise AssertionError("zero-count READ returned data")

    def edge_read_beyond_eof(self):
        size = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes.size
        result = self.call("READ", READ3args(self.file, size + 4096, 32))
        if result.count != 0 or result.data or not result.eof:
            raise AssertionError("READ beyond EOF returned unexpected data")

    def edge_read_max_count(self):
        result = self.call("READ", READ3args(self.file, 0, 0xffffffff))
        if result.data != TEST_DATA or result.count != len(TEST_DATA) or \
                not result.eof:
            raise AssertionError("READ with maximum count returned unexpected data")

    def edge_write_stability(self):
        for stability in (UNSTABLE, DATA_SYNC, FILE_SYNC):
            data = ("stable-%d" % stability).encode("ascii")
            result = self.call("WRITE", WRITE3args(
                self.file, 0, len(data), stability, data))
            if result.count != len(data):
                raise AssertionError("WRITE returned an incorrect byte count")
            if result.committed not in (UNSTABLE, DATA_SYNC, FILE_SYNC) or \
                    result.committed < stability:
                raise AssertionError("WRITE returned weaker stability than requested")
            read = self.call("READ", READ3args(self.file, 0, len(data)))
            if read.data != data:
                raise AssertionError("WRITE data did not persist")
        self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))

    def edge_write_zero_count(self):
        result = self.call("WRITE", WRITE3args(self.file, 0, 0, FILE_SYNC, b""))
        if result.count != 0:
            raise AssertionError("zero-count WRITE returned a nonzero count")

    def edge_write_sparse_offset(self):
        offset = len(TEST_DATA) + 32
        data = b"tail"
        result = self.call("WRITE", WRITE3args(
            self.file, offset, len(data), FILE_SYNC, data))
        if result.count != len(data):
            raise AssertionError("sparse WRITE returned an incorrect count")
        read = self.call("READ", READ3args(self.file, 0, offset + len(data)))
        expected = TEST_DATA + b"\0" * (offset - len(TEST_DATA)) + data
        if read.data != expected:
            raise AssertionError("sparse WRITE returned unexpected gap contents")
        self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))

    def edge_write_offset_overflow(self):
        self._expect_status(
            "WRITE",
            WRITE3args(self.file, 0xffffffffffffffff, 1, UNSTABLE, b"x"),
            [NFS3ERR_FBIG, NFS3ERR_INVAL, NFS3ERR_NOSPC])

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

    def edge_mkdir_exist(self):
        name = self._name("mkdir")
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        attrs = self._expect_status(
            "MKDIR", MKDIR3args(diropargs3(self.directory, name),
                                unset_attributes()),
            [NFS3ERR_EXIST])
        del attrs

    def edge_symlink_exist(self):
        name = self._name("symlink")
        self._symlink(name)
        self._expect_status(
            "SYMLINK",
            SYMLINK3args(diropargs3(self.directory, name),
                         symlinkdata3(unset_attributes(), LINK_DATA)),
            [NFS3ERR_EXIST])

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
                            [NFS3ERR_ISDIR])

    def edge_rmdir_notempty(self):
        name = self._name("nonempty")
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        child_dir = self._lookup(self.directory, name)
        child_name = b"child"
        self._create(child_name, parent=child_dir)
        try:
            self._expect_status("RMDIR", RMDIR3args(
                diropargs3(self.directory, name)), [NFS3ERR_NOTEMPTY])
        finally:
            self.call("REMOVE", REMOVE3args(diropargs3(child_dir, child_name)))
            if child_name in self.created_names:
                self.created_names.remove(child_name)
            self.call("RMDIR", RMDIR3args(diropargs3(self.directory, name)))
            self.created_names.remove(name)

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

    def edge_link_directory(self):
        self._expect_status("LINK", LINK3args(
            self.directory, diropargs3(self.directory, self._name("dirlink"))),
            [NFS3ERR_ISDIR])

    def edge_readdir_cookies(self):
        first = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 4096))
        entries = list(self._entries(first.reply.entries))
        if not entries:
            raise AssertionError("READDIR returned no test entries")
        last = entries[-1]
        if last.cookie == 0:
            raise AssertionError("READDIR returned a zero continuation cookie")
        following = self.call("READDIR", READDIR3args(
            self.directory, last.cookie, first.cookieverf, 4096))
        names = {entry.name for entry in self._entries(following.reply.entries)}
        earlier_names = {entry.name for entry in entries}
        if names & earlier_names:
            raise AssertionError("READDIR cookie repeated earlier entries")

    def edge_readdir_bad_cookie(self):
        self._expect_status(
            "READDIR",
            READDIR3args(self.directory, 0xffffffffffffffff,
                         NULL_VERIFIER, 4096),
            [NFS3ERR_BAD_COOKIE])

    def edge_readdir_bad_verifier(self):
        first = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 4096))
        entries = list(self._entries(first.reply.entries))
        if not entries:
            raise AssertionError("READDIR returned no test entries")
        verifier = first.cookieverf
        bad_verifier = b"\xff" * NFS3_COOKIEVERFSIZE
        if bad_verifier == verifier:
            bad_verifier = b"\xfe" * NFS3_COOKIEVERFSIZE
        self._expect_status(
            "READDIR",
            READDIR3args(self.directory, entries[0].cookie,
                         bad_verifier, 4096),
            [NFS3ERR_BAD_COOKIE])

    def edge_readdirplus_toosmall(self):
        self._expect_status(
            "READDIRPLUS",
            READDIRPLUS3args(self.directory, 0, NULL_VERIFIER, 0, 0),
            [NFS3ERR_TOOSMALL])

    def edge_fsstat_counts(self):
        result = self.call("FSSTAT", FSSTAT3args(self.root))
        if result.fbytes > result.tbytes or result.abytes > result.fbytes:
            raise AssertionError("FSSTAT byte counts are inconsistent")
        if result.ffiles > result.tfiles or result.afiles > result.ffiles:
            raise AssertionError("FSSTAT file counts are inconsistent")

    def edge_fsinfo_limits(self):
        result = self.call("FSINFO", FSINFO3args(self.root))
        if result.rtpref > result.rtmax or result.wtpref > result.wtmax:
            raise AssertionError("FSINFO preferred transfer exceeds maximum")
        if result.time_delta.nseconds >= 1000000000:
            raise AssertionError("FSINFO time_delta nanoseconds are out of range")
        if result.properties & ~(FSF3_LINK | FSF3_SYMLINK |
                                 FSF3_HOMOGENEOUS | FSF3_CANSETTIME):
            raise AssertionError("FSINFO returned undefined property bits")

    def edge_pathconf_name_max(self):
        limits = self.call("PATHCONF", PATHCONF3args(self.directory))
        if limits.name_max > MAX_TEST_NAME_LENGTH:
            raise AssertionError("PATHCONF name_max exceeds safe test limit")
        name = b"m" * limits.name_max
        handle = self._create(name)
        attrs = self.call("GETATTR", GETATTR3args(handle)).obj_attributes
        if attrs.type != NF3REG:
            raise AssertionError("PATHCONF maximum-length name was not created")
        too_long = self._expect_status(
            "CREATE",
            CREATE3args(diropargs3(self.directory, name + b"x"),
                       createhow3(GUARDED,
                                  obj_attributes=unset_attributes())),
            [NFS3ERR_NAMETOOLONG])
        del too_long

    def edge_commit_range(self):
        for offset, count in ((1, 1), (0, 0xffffffff),
                              (0xffffffffffffffff, 0)):
            self.call("COMMIT", COMMIT3args(self.file, offset, count))

    def run(self, selected=None):
        selected = set(selected or ())
        available = {name.lower() for name, _ in self.procedures}
        available.update(name.lower() for name, _, _ in self.edge_cases)
        unknown = selected - available
        if unknown:
            raise ValueError("Unknown NFSv3 procedure(s): %s" %
                             ", ".join(sorted(unknown)))
        cases = [(name, name, method) for name, method in self.procedures]
        cases.extend(self.edge_cases)
        for test_name, procedure, method in cases:
            if selected and procedure.lower() not in selected and \
                    test_name.lower() not in selected:
                continue
            try:
                getattr(self, method)()
                print("PASS %s" % test_name)
            except Exception as error:
                self.failures.append((test_name, error))
                print("FAIL %s: %s" % (test_name, error))
        return self.failures

    def cleanup(self):
        failures = []
        for name in reversed(self.created_names[:]):
            try:
                handle = self._lookup(self.directory, name)
                attrs = self.call("GETATTR", GETATTR3args(handle)).obj_attributes
                if attrs.type == NF3DIR:
                    self.call("RMDIR", RMDIR3args(
                        diropargs3(self.directory, name)))
                else:
                    self.call("REMOVE", REMOVE3args(
                        diropargs3(self.directory, name)))
            except Exception as error:
                failures.append((name, error))
        if self.directory is not None:
            try:
                self.call("RMDIR", RMDIR3args(
                    diropargs3(self.root, self.directory_name)))
            except Exception as error:
                failures.append((self.directory_name, error))
        return failures
