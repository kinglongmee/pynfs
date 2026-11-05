from .base import *
from xdrdef.nfs3_const import *
from xdrdef.nfs3_type import sattrguard3


class SetattrTests:
    def test_setattr(self):
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o600)
        self.call("SETATTR", SETATTR3args(
            self.file, attrs, sattrguard3(FALSE)))
        result = self.call("GETATTR", GETATTR3args(self.file)).obj_attributes
        if result.mode & 0o777 != 0o600:
            raise AssertionError("SETATTR did not update the file mode")


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

    def setattr_file_mode(self):
        name = self._name("setattr-mode")
        handle = self._create(name, mode=0o600)
        attrs = unset_attributes()
        attrs.mode = set_mode3(TRUE, 0o640)
        try:
            self.call("SETATTR", SETATTR3args(
                handle, attrs, sattrguard3(FALSE)))
            result = self.call(
                "GETATTR", GETATTR3args(handle)).obj_attributes
            if result.mode & 0o7777 != 0o640:
                raise AssertionError(
                    "SETATTR mode was not reflected by GETATTR")
        finally:
            self._unlink(name)

    def setattr_file_size(self):
        name = self._name("setattr-size")
        handle = self._create(name, mode=0o600)
        attrs = unset_attributes()
        attrs.size = set_size3(TRUE, 3)
        try:
            self.call("SETATTR", SETATTR3args(
                handle, attrs, sattrguard3(FALSE)))
            size = self.call(
                "GETATTR", GETATTR3args(handle)).obj_attributes.size
            if size != 3:
                raise AssertionError("SETATTR size: expected 3, got %d" % size)
        finally:
            self._unlink(name)
