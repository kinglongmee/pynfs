"""Regression tests for RPC connection establishment."""

import errno
import socket
import unittest
from unittest.mock import Mock, patch

from rpc import rpc


class ConnectionTests(unittest.TestCase):
    address = ("localhost", 20048)
    resolved = [(socket.AF_INET, socket.SOCK_STREAM, 0, "",
                 ("127.0.0.1", 20048))]

    def connect(self):
        handler = Mock()
        return rpc.ConnectionHandler.connect(handler, self.address)

    def test_connection_failure_preserves_original_error(self):
        sock = Mock()
        error = ConnectionRefusedError(errno.ECONNREFUSED,
                                       "Connection refused")
        sock.connect.side_effect = error
        with patch.object(rpc.socket, "getaddrinfo", return_value=self.resolved), \
                patch.object(rpc.socket, "socket", return_value=sock):
            with self.assertRaises(ConnectionRefusedError) as raised:
                self.connect()
        self.assertIs(raised.exception, error)
        sock.close.assert_called_once_with()
        sock.setblocking.assert_not_called()

    def test_socket_creation_failure_preserves_original_error(self):
        error = OSError(errno.EMFILE, "Too many open files")
        with patch.object(rpc.socket, "getaddrinfo", return_value=self.resolved), \
                patch.object(rpc.socket, "socket", side_effect=error):
            with self.assertRaises(OSError) as raised:
                self.connect()
        self.assertIs(raised.exception, error)

    def test_connection_retries_next_address(self):
        failed, connected = Mock(), Mock()
        failed.connect.side_effect = ConnectionRefusedError(
            errno.ECONNREFUSED, "Connection refused")
        with patch.object(rpc.socket, "getaddrinfo",
                          return_value=self.resolved * 2), \
                patch.object(rpc.socket, "socket",
                             side_effect=[failed, connected]), \
                patch.object(rpc, "RpcPipe") as pipe, \
                patch.object(rpc, "DeferredData") as deferred:
            result = self.connect()
        failed.close.assert_called_once_with()
        failed.setblocking.assert_not_called()
        connected.close.assert_not_called()
        connected.setblocking.assert_called_once_with(0)
        pipe.assert_called_once()
        deferred.return_value.wait.assert_called_once_with()
        self.assertIs(result, pipe.return_value)

    def test_empty_address_list_reports_error(self):
        with patch.object(rpc.socket, "getaddrinfo", return_value=[]):
            with self.assertRaisesRegex(OSError, "No socket addresses found"):
                self.connect()


if __name__ == "__main__":
    unittest.main()
