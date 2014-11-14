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

TEMP = "/tmp/bam_test"
# Separate tmp folder for server, since we don't reset the server at every test
TEMP_SERVER = "/tmp/bam_test_server"
PORT = 5555
PROJECT_NAME = "test_project"

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

def svn_repo_checkout(path):
    run(["svn", "checkout", path])

def svn_repo_populate(path):
    dummy_file = os.path.join(path, "file1")
    run(["touch", dummy_file])
    run(["svn", "add", dummy_file])
    run(["svn", "commit", "-m", "First commit"])

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


def server(mode='testing', debug=False):
    """Start development server via Flask app.run() in a separate thread. We need server
    to run in order to check most of the client commands.
    """
    import threading

    def run_testing_server():
        from application import app
        # If we run the server in testing mode (the default) we override sqlite database,
        # with a testing, disposable one (create TMP dir)
        if mode == 'testing':
            from application import db
            from application.modules.projects.model import Project, ProjectSetting
            # Override sqlite database
            if not os.path.isdir(TEMP_SERVER):
                os.makedirs(TEMP_SERVER)
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + TEMP_SERVER + '/bam_test.db'
            # Use the model definitions to create all the tables
            db.create_all()
            # Create a testing project, based on the global configuration (depends on a
            # correct initialization of the SVN repo and on the creation of a checkout)

            # TODO(fsiddi): turn these values in variables
            project = Project(
                name=PROJECT_NAME,
                repository_path="/tmp/bam_test/remote_store/svn_checkout",
                upload_path="/tmp/bam_test/remote_store/upload",
                status="active"
                )
            db.session.add(project)
            db.session.commit()
        # Run the app in production mode (prevents tests to run twice)
        app.run(port=PORT, debug=debug)

    from multiprocessing import Process
    p = Process(target=run_testing_server, args=())
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
        # Create local storage folder
        if not os.path.isdir(self.path_local_store):
            os.makedirs(self.path_local_store)

        # Create remote storage (usually is on the server).
        # SVN repo and SVN checkout will live here
        if not os.path.isdir(self.path_remote_store):
            os.makedirs(self.path_remote_store)

        # Check for SVN repo folder
        path_svn_repo = os.path.join(self.path_remote_store, "svn_repo")
        if not os.path.isdir(path_svn_repo):
            os.makedirs(path_svn_repo)

        # Create a fresh SVN repository
        svn_repo_create(self.proj_name, path_svn_repo)

        # Check for SVN checkout
        path_svn_checkout = os.path.join(self.path_remote_store, "svn_checkout", self.proj_name)
        if not os.path.isdir(path_svn_checkout):
            os.makedirs(path_svn_checkout)

        # Create an SVN checkout of the freshly created repo
        svn_repo_checkout(path_svn_checkout)

        # Pupulate the repo with an empty file
        svn_repo_populate(path_svn_checkout)

    def tearDown(self):
        #input('Wait:')
        shutil.rmtree(TEMP)

    def get_url(self):
        url_full = "%s@%s/%s" % (self.user_name, self.server_addr, self.proj_name)
        user_name, url = url_full.rpartition('@')[0::2]
        return url_full, user_name, url

    def init_defaults(self):
        self.path_local_store = os.path.join(TEMP, "local_store")
        self.path_remote_store = os.path.join(TEMP, "remote_store")

        self.proj_name = PROJECT_NAME
        self.user_name = "user"
        self.server_addr = "http://localhost:%s" % PORT

    def init_repo(self):
        url_full, user_name, url = self.get_url()
        bam_run(["init", url_full], self.path_local_store)


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
        with open(os.path.join(self.path_local_store, self.proj_name, ".bam", "config")) as f:
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

        d = os.path.join(self.path_local_store, self.proj_name)

        stdout, stderr = bam_run(["ls", "--json"], d)

        self.assertEqual("", stderr)

        import json
        ret = json.loads(stdout)


if __name__ == '__main__':
    p = server()
    unittest.main(exit=False)
    p.terminate()

    shutil.rmtree(TEMP_SERVER, ignore_errors=True)

