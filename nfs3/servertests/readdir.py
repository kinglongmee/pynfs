from .base import *
from xdrdef.nfs3_const import *


class ReaddirTests:
    def test_readdir(self):
        result = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 8192))
        names = {entry.name for entry in self._entries(result.reply.entries)}
        if self.file_name not in names:
            raise AssertionError("READDIR omitted the seed file")


    def edge_readdir_cookies(self):
        first = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 4096))
        entries = list(self._entries(first.reply.entries))
        if not entries:
            raise AssertionError("READDIR returned no test entries")
        last = entries[-1]
        if last.cookie == 0:
            raise AssertionError("READDIR returned a zero continuation cookie")
        following = self.call("READDIR", READDIR3args(
            self.directory, last.cookie, first.cookieverf, 4096))
        names = {entry.name for entry in self._entries(following.reply.entries)}
        earlier_names = {entry.name for entry in entries}
        if names & earlier_names:
            raise AssertionError("READDIR cookie repeated earlier entries")


    def edge_readdir_bad_cookie(self):
        self._expect_status(
            "READDIR",
            READDIR3args(self.directory, 0xffffffffffffffff,
                         NULL_VERIFIER, 4096),
            [NFS3ERR_BAD_COOKIE,NFS3_OK,NFS3ERR_INVAL])


    def edge_readdir_bad_verifier(self):
        first = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 4096))
        entries = list(self._entries(first.reply.entries))
        if not entries:
            raise AssertionError("READDIR returned no test entries")
        verifier = first.cookieverf
        bad_verifier = b"\xff" * NFS3_COOKIEVERFSIZE
        if bad_verifier == verifier:
            bad_verifier = b"\xfe" * NFS3_COOKIEVERFSIZE
        self._expect_status(
            "READDIR",
            READDIR3args(self.directory, entries[0].cookie,
                         bad_verifier, 4096),
            [NFS3ERR_BAD_COOKIE])

    def readdir_includes_file(self):
        result = self.call("READDIR", READDIR3args(
            self.directory, 0, NULL_VERIFIER, 8192))
        names = {entry.name for entry in self._entries(result.reply.entries)}
        if self.file_name not in names:
            raise AssertionError("READDIR did not return the standard test file")

    def readdirplus_includes_handle(self):
        args = READDIRPLUS3args(
            self.directory, 0, NULL_VERIFIER, 8192, 8192)
        result = self.client.proc(NFSPROC3_READDIRPLUS, args)
        if result.status == NFS3ERR_NOTSUPP:
            raise NFS3TestUnsupported(
                "Server does not support optional READDIRPLUS")
        if result.status != NFS3_OK:
            self._expect_status("READDIRPLUS", args, [NFS3_OK])
        entries = self._entries(result.resok.reply.entries)
        entry = next((entry for entry in entries
                      if entry.name == self.file_name), None)
        if entry is None:
            raise AssertionError(
                "READDIRPLUS did not return the standard test file")
        if (entry.name_attributes.attributes_follow and
                entry.name_attributes.attributes.type != NF3REG):
            raise AssertionError("READDIRPLUS returned the wrong file type")
        if (entry.name_handle.handle_follows and
                entry.name_handle.handle.data != self.file.data):
            raise AssertionError("READDIRPLUS returned the wrong file handle")
