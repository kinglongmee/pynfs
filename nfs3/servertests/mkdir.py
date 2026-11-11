from .base import *


class MkdirTests:
    def test_mkdir(self):
        name = b"mkdir-test"
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        if self.call("GETATTR", GETATTR3args(
                self._lookup(self.directory, name))).obj_attributes.type != NF3DIR:
            raise AssertionError("MKDIR did not create a directory")


    def edge_mkdir_dot_components(self):
        self._expect_dot_status(
            "MKDIR", lambda where: MKDIR3args(where, unset_attributes()),
            [NFS3ERR_EXIST,NFS3ERR_INVAL])


    def edge_mkdir_exist(self):
        name = self._name("mkdir")
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        attrs = self._expect_status(
            "MKDIR", MKDIR3args(diropargs3(self.directory, name),
                                unset_attributes()),
            [NFS3ERR_EXIST])
        del attrs


    def test_mkdir_dot_components_are_rejected(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests.call = Mock()
        tests.edge_mkdir_dot_components()
        calls = tests._expect_status.call_args_list
        assert len(calls) == 2
        for call, component in zip(calls, (b".", b"..")):
            actual_procedure, args, actual_expected = call[0]
            assert actual_procedure == "MKDIR"
            unpacker = NFS3Unpacker(tests._pack_args(args))
            decoded = getattr(
                unpacker, "unpack_" + args.__class__.__name__)()
            assert decoded.where.name == component
            assert actual_expected == [NFS3ERR_EXIST, NFS3ERR_INVAL]
        assert tests._check_dot_namespace.call_count == 2
