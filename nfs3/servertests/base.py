"""NFSv3 procedure tests based on RFC 1813."""

import os
import struct
from unittest.mock import Mock

import use_local
import rpc.rpc as rpc
from nfs3client import NFS3Client
from xdrdef.nfs3_pack import NFS3Packer, NFS3Unpacker
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


class NFS3TestUnsupported(Exception):
    pass


class NFS3TestBase:
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


    def _create(self, name, parent=None, mode=None):
        attrs = unset_attributes()
        if mode is not None:
            attrs.mode = set_mode3(TRUE, mode)
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


    @staticmethod
    def _entries(head):
        while head:
            if isinstance(head, list):
                if not head:
                    return
                head = head[0]
            yield head
            head = head.nextentry


    def _check_dot_namespace(self):
        self.edge_lookup_dot_components()
        if self._lookup(self.root, self.directory_name).data != \
                self.directory.data:
            raise AssertionError("namespace request changed the test directory")
        if self._lookup(self.directory, self.file_name).data != self.file.data:
            raise AssertionError("namespace request changed the seed file")


    def _expect_dot_status(self, procedure, make_args, expected):
        for component in (b".", b".."):
            self._expect_status(procedure, make_args(
                diropargs3(self.directory, component)), expected)
            self._check_dot_namespace()


    @staticmethod
    def _pack_args(args):
        packer = NFS3Packer()
        getattr(packer, "pack_" + args.__class__.__name__)(args)
        return packer.get_buffer()


    def _expect_garbage_args(self, procedure, payload):
        pipe = self.client.get_pipe()
        xid = self.client.send_call(
            pipe, globals()["NFSPROC3_" + procedure], payload,
            self.client.default_cred)
        try:
            pipe.listen(xid, timeout=10.0)
        except rpc.RPCAcceptError as error:
            if error.stat == rpc.GARBAGE_ARGS:
                return
            raise
        raise AssertionError("%s accepted malformed arguments" % procedure)


    def run(self, selected=None):
        selected = set(selected or ())
        available = {value.lower() for name, procedure, _ in self.procedures
                     for value in (name, procedure)}
        unknown = selected - available
        if unknown:
            raise ValueError("Unknown NFSv3 procedure(s): %s" %
                             ", ".join(sorted(unknown)))
        for test_name, procedure, method in self.procedures:
            if selected and procedure.lower() not in selected and \
                    test_name.lower() not in selected:
                continue
            try:
                getattr(self, method)()
                print("PASS %s" % test_name)
            except NFS3TestUnsupported as error:
                print("UNSUPPORTED %s: %s" % (test_name, error))
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
