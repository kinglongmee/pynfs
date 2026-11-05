from .base import *
from xdrdef.nfs3_const import *


class WriteTests:
    def test_write(self):
        result = self.call("WRITE", WRITE3args(
            self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))
        if result.count != len(TEST_DATA) or result.committed != FILE_SYNC:
            raise AssertionError("WRITE returned an unexpected count or stability")


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


    def edge_write_binary_payload(self):
        data = bytes(range(256)) + b"\x00\xff\xfe"
        try:
            result = self.call("WRITE", WRITE3args(
                self.file, 0, len(data), FILE_SYNC, data))
            if result.count != len(data):
                raise AssertionError("WRITE returned an incorrect binary count")
            returned = self.call(
                "READ", READ3args(self.file, 0, len(data))).data
            if returned != data:
                raise AssertionError("READ changed opaque binary file data")
        finally:
            self.call("WRITE", WRITE3args(
                self.file, 0, len(TEST_DATA), FILE_SYNC, TEST_DATA))


    def write_count(self):
        for count, data in ((0, b"x"), (2, b"x"), (1, b""), (1, b"xy")):
            args = WRITE3args(self.file, 0, count, FILE_SYNC, data)
            self._expect_garbage_args("WRITE", self._pack_args(args))


    def write_stability(self):
        prefix = self._pack_args(GETATTR3args(self.file))
        for stable in (3, 0xffffffff):
            payload = prefix + struct.pack(">QIII", 0, 0, stable, 0)
            self._expect_garbage_args("WRITE", payload)


    def write_truncated(self):
        payload = self._pack_args(WRITE3args(
            self.file, 0, 8, FILE_SYNC, b"abcdefgh"))
        self._expect_garbage_args("WRITE", payload[:-4])

    def write_and_read_back(self):
        name = self._name("write-readback")
        handle = self._create(name, mode=0o600)
        data = b"NFSv3 write test"
        try:
            result = self.call("WRITE", WRITE3args(
                handle, 0, len(data), FILE_SYNC, data))
            if result.count != len(data):
                raise AssertionError(
                    "WRITE returned count %d, expected %d" %
                    (result.count, len(data)))
            if result.committed != FILE_SYNC:
                raise AssertionError(
                    "WRITE did not satisfy FILE_SYNC stability request")
            read = self.call("READ", READ3args(handle, 0, len(data)))
            if read.data != data:
                raise AssertionError("READ data differs from WRITE data")
        finally:
            self._unlink(name)

    def write_zero_length(self):
        name = self._name("write-zero")
        handle = self._create(name, mode=0o600)
        try:
            result = self.call(
                "WRITE", WRITE3args(handle, 0, 0, UNSTABLE, b""))
            if result.count != 0:
                raise AssertionError(
                    "zero-count WRITE returned count %d" % result.count)
        finally:
            self._unlink(name)

    def test_write_count_mismatches_survive_encoding(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.write_count()
        calls = tests._expect_garbage_args.call_args_list
        assertions.assertEqual(len(calls), 4)
        for call in calls:
            procedure, payload = call[0]
            assertions.assertEqual(procedure, "WRITE")
            args = NFS3Unpacker(payload).unpack_WRITE3args()
            assertions.assertNotEqual(args.count, len(args.data))

    def test_invalid_write_stability_payloads(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.write_stability()
        calls = tests._expect_garbage_args.call_args_list
        assertions.assertEqual(len(calls), 2)
        for call in calls:
            assertions.assertEqual(call[0][0], "WRITE")
            assertions.assertIsInstance(call[0][1], bytes)

    def test_truncated_write_payload(self):
        assertions = unittest.TestCase()
        from . import NFS3Tests
        tests = object.__new__(NFS3Tests)
        tests.directory = nfs_fh3(b"directory")
        tests.file = nfs_fh3(b"file")
        tests._serial = 0
        tests.client = Mock()
        tests._expect_garbage_args = Mock()
        tests.write_truncated()
        tests._expect_garbage_args.assert_called_once()
        assertions.assertEqual(
            tests._expect_garbage_args.call_args[0][0], "WRITE")
