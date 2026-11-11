from .base import *


class RmdirTests:
    def test_rmdir(self):
        name = b"rmdir-test"
        self._mkdir(self.directory, name)
        self.created_names.append(name)
        self.call("RMDIR", RMDIR3args(diropargs3(self.directory, name)))
        self.created_names.remove(name)


    def edge_rmdir_dot_components(self):
        self._expect_dot_status("RMDIR", RMDIR3args, [NFS3ERR_ACCES,NFS3ERR_INVAL])


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

    def test_rmdir_dot_components_are_rejected(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests.call = Mock()
        tests.edge_rmdir_dot_components()
        calls = tests._expect_status.call_args_list
        assert len(calls) == 2
        for call, component in zip(calls, (b".", b"..")):
            actual_procedure, args, actual_expected = call[0]
            assert actual_procedure == "RMDIR"
            unpacker = NFS3Unpacker(tests._pack_args(args))
            decoded = getattr(
                unpacker, "unpack_" + args.__class__.__name__)()
            assert decoded.object.name == component
            assert actual_expected == [NFS3ERR_ACCES, NFS3ERR_INVAL]
        assert tests._check_dot_namespace.call_count == 2
