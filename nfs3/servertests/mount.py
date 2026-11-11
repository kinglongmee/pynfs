"""Offline regression and procedure tests for the NFSv3 MOUNT client."""

import os
import struct
import sys
from unittest.mock import Mock

sys.path.insert(
    0, os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "nfs4.1")))

from nfs3client import Mnt3Client
from rpc.rpc import RPCError, RPCTimeout
from xdrdef.mnt3_const import (
    FHSIZE3,
    MNTPATHLEN,
    MNT3_OK,
    MNT3ERR_ACCES,
    MOUNTPROC3_DUMP,
    MOUNTPROC3_EXPORT,
    MOUNTPROC3_MNT,
    MOUNTPROC3_NULL,
    MOUNTPROC3_UMNT,
    MOUNTPROC3_UMNTALL,
    mountstat3,
)
from xdrdef.mnt3_pack import MNT3Packer, MNT3Unpacker, XDRError
from xdrdef.mnt3_type import mountres3, mountres3_ok


class dirpath(bytes):
    pass


class ResponsePipe:
    def __init__(self):
        self.response = b""

    def is_active(self):
        return True

    def listen(self, xid, timeout):
        return None, self.response


class Mounttests:
    @staticmethod
    def _mount3_client():
        client = object.__new__(Mnt3Client)
        client._pipe = ResponsePipe()
        client.default_cred = object()
        client.send_call = Mock(return_value=1)
        return client

    @staticmethod
    def _mount3_call(client, procedure, argument, result_type, response=b""):
        client._pipe.response = response
        result = client.proc(procedure, argument, result_type)

        pipe, sent_procedure, payload, credential = \
            client.send_call.call_args[0]
        if pipe is not client._pipe:
            raise AssertionError("MOUNT request used the wrong pipe")
        if sent_procedure != procedure:
            raise AssertionError("MOUNT request used the wrong procedure")
        if credential is not client.default_cred:
            raise AssertionError("MOUNT request used the wrong credential")
        if argument is None:
            expected = b""
        else:
            expected = struct.pack(">I", len(argument)) + argument
            expected += b"\0" * (-len(argument) % 4)
        if payload != expected:
            raise AssertionError(
                "MOUNT procedure %d encoded incorrect arguments for %r" %
                (procedure, argument))
        return result

    @staticmethod
    def _mount3_pack_result(type_name, result):
        packer = MNT3Packer()
        getattr(packer, "pack_" + type_name)(result)
        return packer.get_buffer()

    def test_mount3_get_rootfh_text_export(self):
        response = mountres3(MNT3_OK, mountres3_ok(b"test-handle", []))
        client = object.__new__(Mnt3Client)
        client.proc = Mock(return_value=response)
        handle = client.get_rootfh(["nfs/"])
        proc, argument, result_type = client.proc.call_args[0]
        if proc != MOUNTPROC3_MNT or result_type != "mountres3":
            raise AssertionError("get_rootfh sent an incorrect MOUNT request")
        expected = b"/nfs/"
        encoded = struct.pack(">I", len(expected)) + expected
        encoded += b"\0" * (-len(expected) % 4)
        packer = MNT3Packer()
        packer.pack_dirpath(argument)
        if packer.get_buffer() != encoded:
            raise AssertionError("get_rootfh encoded the export path incorrectly")
        if handle != b"test-handle":
            raise AssertionError("get_rootfh returned the wrong file handle")

    def test_mount3_get_rootfh_byte_export_components(self):
        response = mountres3(MNT3_OK, mountres3_ok(b"test-handle", []))
        client = object.__new__(Mnt3Client)
        client.proc = Mock(return_value=response)
        handle = client.get_rootfh([b"nfs", b"subdir"])
        argument = client.proc.call_args[0][1]
        packer = MNT3Packer()
        packer.pack_dirpath(argument)
        unpacker = MNT3Unpacker(packer.get_buffer())
        path = unpacker.unpack_dirpath()
        unpacker.done()
        if path != b"/nfs/subdir" or handle != b"test-handle":
            raise AssertionError(
                "get_rootfh did not preserve byte export components")

    def test_mount3_get_rootfh_error_reports_status(self):
        client = object.__new__(Mnt3Client)
        client.proc = Mock(return_value=mountres3(MNT3ERR_ACCES))
        try:
            client.get_rootfh(["nfs"])
        except RPCError as error:
            if "MNT3ERR_ACCES" not in str(error):
                raise AssertionError("MOUNT error omitted the status name")
        else:
            raise AssertionError("get_rootfh accepted a failed MOUNT response")

    def test_mount3_null(self):
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_NULL, None, "void")
        if result != b"":
            raise AssertionError("MOUNT NULL returned a nonempty result")

    def test_mount3_mnt(self):
        response = mountres3(MNT3_OK, mountres3_ok(b"test-handle", []))
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_MNT, dirpath(b"/export"),
            "mountres3", self._mount3_pack_result("mountres3", response))
        if result.fhs_status != MNT3_OK:
            raise AssertionError("MOUNT MNT decoded the wrong status")
        if result.mountinfo.fhandle != b"test-handle":
            raise AssertionError("MOUNT MNT decoded the wrong file handle")

    def test_mount3_dump(self):
        response = self._mount3_pack_result("mountlist", [])
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_DUMP, None, "mountlist",
            response)
        if result != []:
            raise AssertionError("MOUNT DUMP decoded a nonempty mount list")

    def test_mount3_umnt(self):
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_UMNT, dirpath(b"/export"),
            "void")
        if result != b"":
            raise AssertionError("MOUNT UMNT returned a nonempty result")

    def test_mount3_umntall(self):
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_UMNTALL, None, "void")
        if result != b"":
            raise AssertionError("MOUNT UMNTALL returned a nonempty result")

    def test_mount3_export(self):
        response = self._mount3_pack_result("exports", [])
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_EXPORT, None, "exports",
            response)
        if result != []:
            raise AssertionError("MOUNT EXPORT decoded a nonempty export list")

    def _mount3_check_paths(self, procedure, result_type, response=b""):
        client = self._mount3_client()
        paths = (
            b"", b"/", b"/export/", b"/export/subdir",
            b"/export/\xff\xfe", b"/" + b"x" * (MNTPATHLEN - 2),
            b"/" + b"x" * (MNTPATHLEN - 1),
        )
        for path in paths:
            self._mount3_call(
                client, procedure, dirpath(path), result_type, response)

    def test_mount3_mnt_paths(self):
        response = self._mount3_pack_result(
            "mountres3", mountres3(MNT3_OK, mountres3_ok(b"handle", [])))
        self._mount3_check_paths(MOUNTPROC3_MNT, "mountres3", response)

    def test_mount3_umnt_paths(self):
        self._mount3_check_paths(MOUNTPROC3_UMNT, "void")

    def _mount3_check_oversized_path(self, procedure, result_type):
        client = self._mount3_client()
        try:
            client.proc(
                procedure, dirpath(b"/" + b"x" * MNTPATHLEN), result_type)
        except XDRError:
            client.send_call.assert_not_called()
        else:
            raise AssertionError(
                "MOUNT procedure %d accepted an oversized path" % procedure)

    def test_mount3_mnt_oversized_path(self):
        self._mount3_check_oversized_path(MOUNTPROC3_MNT, "mountres3")

    def test_mount3_umnt_oversized_path(self):
        self._mount3_check_oversized_path(MOUNTPROC3_UMNT, "void")

    def test_mount3_mnt_error_statuses(self):
        client = self._mount3_client()
        for status, name in mountstat3.items():
            if status == MNT3_OK:
                continue
            response = struct.pack(">i", status)
            result = self._mount3_call(
                client, MOUNTPROC3_MNT, dirpath(b"/export"), "mountres3",
                response)
            if result.fhs_status != status or result.mountinfo is not None:
                raise AssertionError("MOUNT MNT incorrectly decoded %s" % name)
            try:
                client.get_rootfh([b"export"])
            except RPCError as error:
                if name not in str(error):
                    raise AssertionError(
                        "MOUNT error did not report %s: %s" % (name, error))
            else:
                raise AssertionError("MOUNT get_rootfh accepted %s" % name)

    def test_mount3_mnt_handle_and_auth_flavors(self):
        handle = bytes(range(FHSIZE3))
        flavors = [0, 1, 6]
        response = self._mount3_pack_result(
            "mountres3", mountres3(MNT3_OK, mountres3_ok(handle, flavors)))
        result = self._mount3_call(
            self._mount3_client(), MOUNTPROC3_MNT, dirpath(b"/export"),
            "mountres3", response)
        if result.mountinfo.fhandle != handle:
            raise AssertionError("MOUNT MNT decoded the wrong file handle")
        if result.mountinfo.auth_flavors != flavors:
            raise AssertionError("MOUNT MNT decoded incorrect auth flavors")

    def test_mount3_mnt_truncated_response(self):
        client = self._mount3_client()
        response = self._mount3_pack_result(
            "mountres3", mountres3(MNT3_OK, mountres3_ok(b"handle", [1])))
        for length in (4, 8, 12, len(response) - 4):
            client._pipe.response = response[:length]
            try:
                client.proc(
                    MOUNTPROC3_MNT, dirpath(b"/export"), "mountres3")
            except EOFError:
                continue
            raise AssertionError(
                "MOUNT MNT accepted a reply truncated to %d bytes" % length)

    def test_mount3_mount_unmount_timeouts(self):
        client = self._mount3_client()
        client._pipe.listen = Mock(side_effect=RPCTimeout())
        for procedure, argument, result_type in (
                (MOUNTPROC3_MNT, dirpath(b"/export"), "mountres3"),
                (MOUNTPROC3_UMNT, dirpath(b"/export"), "void"),
                (MOUNTPROC3_UMNTALL, None, "void")):
            try:
                client.proc(procedure, argument, result_type)
            except RPCTimeout:
                continue
            raise AssertionError(
                "MOUNT procedure %d did not propagate a timeout" % procedure)
