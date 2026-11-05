from .base import *


class ReaddirplusTests:
    def test_readdirplus(self):
        result = self.call("READDIRPLUS", READDIRPLUS3args(
            self.directory, 0, NULL_VERIFIER, 8192, 16384))
        entries = list(self._entries(result.reply.entries))
        entry = next((e for e in entries if e.name == self.file_name), None)
        if entry is None:
            raise AssertionError("READDIRPLUS omitted the seed file")
        if entry.name_handle.handle_follows and \
                entry.name_handle.handle.data != self.file.data:
            raise AssertionError("READDIRPLUS returned the wrong file handle")
        if entry.name_attributes.attributes_follow and \
                entry.name_attributes.attributes.type != NF3REG:
            raise AssertionError("READDIRPLUS returned the wrong file attributes")


    def edge_readdirplus_toosmall(self):
        self._expect_status(
            "READDIRPLUS",
            READDIRPLUS3args(self.directory, 0, NULL_VERIFIER, 0, 0),
            [NFS3ERR_TOOSMALL])
