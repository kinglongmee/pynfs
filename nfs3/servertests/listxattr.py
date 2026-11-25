"""LISTXATTR tests for the OpenFS NFSv3 xattr extension."""

from .getxattr import CREATE, LISTXATTR, SETXATTR, XattrTestBase


class ListxattrTests(XattrTestBase):
    def test_listxattr(self):
        filename, handle = self._xattr_file("listxattr")
        try:
            _, eof, names = self._xattr_call(LISTXATTR, handle)
            if names or not eof:
                raise AssertionError("new file has unexpected xattrs")

            expected = {("user.pynfs.list.%02d" % i).encode("ascii")
                        for i in range(20)}
            for key in sorted(expected):
                self._xattr_call(SETXATTR, handle, key, b"value", CREATE)

            names = []
            seen_cookies = {0}
            cookie = 0
            page_count = 0
            while True:
                cookie, eof, page = self._xattr_call(
                    LISTXATTR, handle, cookie=cookie, maxcount=64)
                page_count += 1
                names.extend(page)
                if eof:
                    break
                if not page or cookie in seen_cookies:
                    raise AssertionError("LISTXATTR did not advance its cookie")
                seen_cookies.add(cookie)
                if len(names) > len(expected):
                    raise AssertionError("LISTXATTR repeated names")
            if page_count < 2:
                raise AssertionError("LISTXATTR did not paginate its results")
            if len(names) != len(expected) or set(names) != expected:
                raise AssertionError("LISTXATTR returned incorrect names")
        finally:
            self._unlink(filename)
