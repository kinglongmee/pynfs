from .base import *


class PathconfTests:
    def test_pathconf(self):
        result = self.call("PATHCONF", PATHCONF3args(self.directory))
        if result.linkmax < 1 or result.name_max < 1:
            raise AssertionError("PATHCONF returned an invalid limit")


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
