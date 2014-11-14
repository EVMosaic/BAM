#!/usr/bin/env python3
# Apache License, Version 2.0

"""
Test bam command line client
"""

# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client", "cli"))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------


# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webservice", "bam"))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------





import os
import sys
import shutil
import json

TEMP = "/tmp/test"
PORT = 5555

def run(cmd, cwd=None):
    # print(">>> ", " ".join(cmd))
    import subprocess
    kwargs = dict(
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        )
    if cwd is not None:
        kwargs["cwd"] = cwd

    proc = subprocess.Popen(cmd, **kwargs)
    stderr, stdout = proc.communicate()

    return stdout


class CHDir:
    __slots__ = (
        "dir_old",
        "dir_new",
        )
    def __init__(self, directory):
        self.dir_old = os.getcwd()
        self.dir_new = directory

    def __enter__(self):
        os.chdir(self.dir_new)

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.dir_old)


class StdIO:
    __slots__ = (
        "stdout",
        "stderr",
        )
    def __init__(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr

    def read(self):
        sys.stdout.seek(0)
        sys.stderr.seek(0)
        return sys.stdout.read(), sys.stderr.read()

    def __enter__(self):
        import io
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self.stdout
        sys.stderr = self.stderr


def svn_repo_create(id_, dirname):
    run(["svnadmin", "create", id_], cwd=dirname)


def bam_run(argv, cwd=None):

    with CHDir(cwd):
        import bam
        with StdIO() as fakeio:
            bam.main(argv)
            ret = fakeio.read()

    return ret

#if __name__ == "__main__":
#    main()


# ------------------------------------------------------------------------------
# Server


def server():
    import threading

    def _():
        from application import app
        app.run(port=PORT, debug=False)


    from multiprocessing import Process
    p = Process(target=_, args=())
    p.start()

    os.system("sleep 1")
    return p


# ------------------------------------------------------------------------------
# Unit Tests

import unittest


class BamSessionTestCase(unittest.TestCase):

    def setUp(self):
        if not os.path.isdir(TEMP):
            os.makedirs(TEMP)

        if not os.path.isdir(self.path_repo):
            os.makedirs(self.path_repo)

        if not os.path.isdir(self.path_remote):
            os.makedirs(self.path_remote)

        svn_repo_create(self.proj_name, self.path_repo)

    def tearDown(self):
        shutil.rmtree(TEMP)

    def get_url(self):
        url_full = "%s@%s/%s" % (self.user_name, self.server_addr, self.proj_name)
        user_name, url = url_full.rpartition('@')[0::2]
        return url_full, user_name, url

    def init_defaults(self):
        self.path_repo = os.path.join(TEMP, "remote_store")
        self.path_remote = os.path.join(TEMP, "local_store")

        self.proj_name = "test"
        self.user_name = "user"
        self.server_addr = "http://localhost:%s" % PORT

    def init_repo(self):
        url_full, user_name, url = self.get_url()
        bam_run(["init", url_full], self.path_remote)


class BamInitTest(BamSessionTestCase):
    """Test the `bam init user@http://bamserver/projectname` command.
    We verify that a project folder is created, and that it contains a .bam subfolder
    with a config file, with the right url and user values (given in the command)
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_init(self):
        self.init_repo()

        url_full, user_name, url = self.get_url()
        with open(os.path.join(self.path_remote, self.proj_name, ".bam", "config")) as f:
            cfg = json.load(f)
            self.assertEqual(url, cfg["url"])
            self.assertEqual(user_name, cfg["user"])


class BamListTest(BamSessionTestCase):
    """Test for the `bam ls --json` command. We run it with --json for easier command
    output parsing. 
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_ls(self):
        self.init_repo()

        d = os.path.join(self.path_remote, self.proj_name)
        stdout, stderr = bam_run(["ls", "--json"], d)

        self.assertEqual("", stderr)

        import json
        ret = json.loads(stdout)


if __name__ == '__main__':
    p = server()
    unittest.main(exit=False)
    p.terminate()

