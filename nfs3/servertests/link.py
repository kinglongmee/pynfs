from .base import *
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import diropargs3


class LinkTests:
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


    def edge_link_dot_components(self):
        before = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        self._expect_dot_status(
            "LINK", lambda where: LINK3args(self.file, where),
            [NFS3ERR_EXIST,NFS3ERR_INVAL])
        after = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if after.nlink != before.nlink:
            raise AssertionError("rejected LINK changed the link count")


    def edge_link_directory(self):
        self._expect_status("LINK", LINK3args(
            self.directory, diropargs3(self.directory, self._name("dirlink"))),
            [NFS3ERR_ISDIR])

    def link_same_file_handle(self):
        name = self._name("hard-link")
        handle = self._create(name, mode=0o600)
        link_name = name + b".link"
        self.call("LINK", LINK3args(
            handle, diropargs3(self.directory, link_name)))
        self.created_names.append(link_name)
        try:
            if self._lookup(self.directory, link_name).data != handle.data:
                raise AssertionError("LINK did not reference the original file")
        finally:
            self._unlink(link_name)
            self._unlink(name)

    def test_link_dot_components_are_rejected(self):
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_status = Mock()
        tests._check_dot_namespace = Mock()
        tests.call = Mock()
        tests.edge_link_dot_components()
        calls = tests._expect_status.call_args_list
        assert len(calls) == 2
        for call, component in zip(calls, (b".", b"..")):
            actual_procedure, args, actual_expected = call[0]
            assert actual_procedure == "LINK"
            unpacker = NFS3Unpacker(tests._pack_args(args))
            decoded = getattr(
                unpacker, "unpack_" + args.__class__.__name__)()
            assert decoded.link.name == component
            assert actual_expected == [NFS3ERR_EXIST, NFS3ERR_INVAL]
        assert tests._check_dot_namespace.call_count == 2
