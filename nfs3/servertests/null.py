from .base import *
from unittest.mock import Mock

from nfs3client import NFS3Client


class NullTests:
    def test_null(self):
        self.client.null()

    def test_null_uses_empty_bytes(self):
        client = object.__new__(NFS3Client)
        client.get_pipe = Mock()
        client.send_call = Mock()
        client.null_async()
        client.send_call.assert_called_once_with(
            client.get_pipe.return_value, 0, b"")
