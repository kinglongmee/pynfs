#!/usr/bin/env python3
"""Run the RFC 1813 NFSv3 procedure tests against an exported filesystem."""

import argparse
import os
import sys

test_dir = os.path.abspath(os.path.dirname(__file__))
repo_dir = os.path.dirname(test_dir)
sys.path.insert(0, test_dir)
sys.path.insert(0, repo_dir)
sys.path.insert(0, os.path.join(repo_dir, "nfs4.1"))

from nfs3.servertests import NFS3Tests


def main():
    parser = argparse.ArgumentParser(
        description="Run NFSv3 RFC 1813 RPC tests")
    parser.add_argument("server", nargs="?",
                        help="NFS server hostname or address")
    parser.add_argument("export", nargs="?",
                        help="Export path mounted for the test run")
    parser.add_argument("--port", type=int,
                        help="NFSv3 TCP port (default: query portmapper)")
    parser.add_argument("--uid", type=int, default=os.getuid(),
                        help="AUTH_SYS user id (default: current user)")
    parser.add_argument("--gid", type=int, default=os.getgid(),
                        help="AUTH_SYS group id (default: current group)")
    parser.add_argument("--list", action="store_true",
                        help="List all NFSv3 test cases and exit")
    parser.add_argument("procedures", nargs="*",
                        help="Optional procedure names to run")
    args = parser.parse_args()

    if args.list:
        for name, _, _ in NFS3Tests.procedures:
            print(name)
        return 0
    if not args.server or not args.export:
        parser.error("server and export are required unless --list is used")
    selected = {name.lower() for name in args.procedures}
    available = {value.lower() for name, procedure, _ in NFS3Tests.procedures
                 for value in (name, procedure)}
    unknown = selected - available
    if unknown:
        parser.error("unknown procedure(s): %s" % ", ".join(sorted(unknown)))

    tests = NFS3Tests(args.server, args.export, args.port, args.uid, args.gid)
    failures = []
    try:
        failures = tests.run(selected)
    finally:
        cleanup_failures = tests.cleanup()
        for name, error in cleanup_failures:
            print("CLEANUP FAILED %s: %s" % (name, error))
    return 1 if failures or cleanup_failures else 0


if __name__ == "__main__":
    sys.exit(main())
