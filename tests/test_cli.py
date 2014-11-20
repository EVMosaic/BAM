#!/usr/bin/env python3
# Apache License, Version 2.0

"""
Test bam command line client

Run all tests:

   python3 test_cli.py

Run a single test:

   python3 -m unittest test_cli.BamCommitTest.test_checkout
"""

VERBOSE = 1

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


# -----------------------------------------
# Ensure we get stdout & stderr on sys.exit
if 1:
    import sys

    def exit(status):
        import io
        globals().update(sys.exit.exit_data)
        if isinstance(sys.stdout, io.StringIO):

            _stdout.write("\nsys.exit(%d) with message:\n" % status)

            sys.stdout.seek(0)
            sys.stderr.seek(0)
            _stdout.write(sys.stdout.read())
            _stderr.write(sys.stderr.read())

            _stdout.write("\n")

            _stdout.flush()
            _stderr.flush()
        _exit(status)

    exit.exit_data = {
        "_exit": sys.exit,
        "_stdout": sys.stdout,
        "_stderr": sys.stderr,
        }
    sys.exit = exit
    del exit
    del sys
# --------

# --------------------------------------------
# Don't Exit when argparse fails to parse args
import argparse
def argparse_fake_exit(self, status, message):
    sys.__stdout__.write(message)
    raise Exception(message)

argparse.ArgumentParser.exit = argparse_fake_exit
del argparse_fake_exit
del argparse
# --------


# ----------------------------------------------------------------------------
# Real beginning of code!

import os
import sys
import shutil
import json

TEMP = "/tmp/bam_test"
# Separate tmp folder for server, since we don't reset the server at every test
TEMP_SERVER = "/tmp/bam_test_server"
PORT = 5555
PROJECT_NAME = "test_project"

# running scripts next to this one!
CURRENT_DIR = os.path.dirname(__file__)


def run(cmd, cwd=None):
    if VERBOSE:
        print(">>> ", " ".join(cmd))
    import subprocess
    kwargs = dict(
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        )
    if cwd is not None:
        kwargs["cwd"] = cwd

    proc = subprocess.Popen(cmd, **kwargs)
    stdout, stderr = proc.communicate()
    returncode = proc.returncode

    if VERBOSE:
        sys.stdout.write("   stdout:  %s\n" % stdout.strip())
        sys.stdout.write("   stderr:  %s\n" % stderr.strip())
        sys.stdout.write("   return:  %d\n" % returncode)

    return stdout, stderr, returncode


def run_check(cmd, cwd=None, returncode_ok=(0,)):
    stdout, stderr, returncode = run(cmd, cwd)
    if returncode in returncode_ok:
        return True

    # verbose will have already printed
    if not VERBOSE:
        print(">>> ", " ".join(cmd))
        sys.stdout.write("   stdout:  %s\n" % stdout.strip())
        sys.stdout.write("   stderr:  %s\n" % stderr.strip())
        sys.stdout.write("   return:  %d\n" % returncode)
    return False


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
        if exc_type is not None:
            self.stdout.write("\n".join(self.read()))

        sys.stdout = self.stdout
        sys.stderr = self.stderr


def svn_repo_create(id_, dirname):
    return run_check(["svnadmin", "create", id_], cwd=dirname)


def svn_repo_checkout(repo, path):
    return run_check(["svn", "checkout", repo, path])


def svn_repo_populate(path):
    if not os.path.exists(path):
        os.makedirs(path)

    # TODO, we probably want to define files externally, for now this is just to see it works
    dummy_file = os.path.join(path, "file1")
    file_quick_touch(dummy_file)

    # adds all files recursively
    if not run_check(["svn", "add", path]):
        return False

    if not run_check(["svn", "commit", "-m", "First commit"], path):
        return False

    return True


def bam_run(argv, cwd=None):
    with CHDir(cwd):
        import bam

        if VERBOSE:
            sys.stdout.write("\n  running:  ")
            if cwd is not None:
                sys.stdout.write("cd %r ; " % cwd)
            sys.stdout.write("bam %s\n" % " ".join(argv))
            # input('press_key!:')

        with StdIO() as fakeio:
            bam.main(argv)
            ret = fakeio.read()

        if VERBOSE:
            sys.stdout.write("   stdout:  %s\n" % ret[0].strip())
            sys.stdout.write("   stderr:  %s\n" % ret[1].strip())

    return ret


def file_quick_write(path, filepart=None, data=None):
    """Quick file creation utility.
    """
    if data is None:
        data = b''
    elif type(data) is bytes:
        mode = 'wb'
    elif type(data) is str:
        mode = 'w'
    else:
        raise Exception("type %r not known" % type(data))

    if filepart is not None:
        path = os.path.join(path, filepart)

    with open(path, mode) as f:
        f.write(data)

def file_quick_read(path, filepart=None, mode='rb'):

    if filepart is not None:
        path = os.path.join(path, filepart)

    with open(path, mode) as f:
        return f.read()


def file_quick_touch(path, filepart=None, times=None):
    if filepart is not None:
        path = os.path.join(path, filepart)
    with open(path, 'a'):
        os.utime(path, times)


def wait_for_input():
    """for debugging,
    so we can inspect the state of the system before the test finished.
    """
    input('press any key to continue:')

# ------------------------------------------------------------------------------
# Server


def server(mode='testing', debug=False):
    """Start development server via Flask app.run() in a separate thread. We need server
    to run in order to check most of the client commands.
    """

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
                status="active",
                )
            db.session.add(project)
            db.session.commit()

            setting = ProjectSetting(
                project_id=project.id,
                name="svn_password",
                value="my_password",
                data_type="str",
                )
            db.session.add(setting)
            db.session.commit()

            setting = ProjectSetting(
                project_id=project.id,
                name="svn_default_user",
                value="my_user",
                data_type="str",
                )
            db.session.add(setting)
            db.session.commit()

        # Run the app in production mode (prevents tests to run twice)
        app.run(port=PORT, debug=debug)

    from multiprocessing import Process
    p = Process(target=run_testing_server, args=())
    p.start()

    os.system("sleep 1")
    return p


def global_setup():

    if VERBOSE:
        # for server
        import logging
        logging.basicConfig(level=logging.DEBUG)
        del logging

    shutil.rmtree(TEMP_SERVER, ignore_errors=True)
    shutil.rmtree(TEMP, ignore_errors=True)
    p = server()
    data = p
    return data


def global_teardown(data):
    p = data
    p.terminate()
    shutil.rmtree(TEMP, ignore_errors=True)


# ------------------------------------------------------------------------------
# Unit Tests

import unittest


class BamSessionTestCase(unittest.TestCase):

    def setUp(self):

        # for running single tests
        if __name__ != "__main__":
            self._data = global_setup()

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
        if not svn_repo_create(self.proj_name, path_svn_repo):
            self.fail("svn_repo: create")

        # Check for SVN checkout
        path_svn_checkout = os.path.join(self.path_remote_store, "svn_checkout")

        # Create an SVN checkout of the freshly created repo
        path_svn_repo_url = "file://%s" % os.path.join(path_svn_repo, self.proj_name)
        if not svn_repo_checkout(path_svn_repo_url, path_svn_checkout):
            self.fail("svn_repo: checkout %r" % path_svn_repo_url)

        # Populate the repo with an empty file
        if not svn_repo_populate(os.path.join(path_svn_checkout, self.proj_name)):
            self.fail("svn_repo: populate")

    def tearDown(self):
        # input('Wait:')
        shutil.rmtree(TEMP)

        # for running single tests
        if __name__ != "__main__":
            global_teardown(self._data)

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


class BamCommitTest(BamSessionTestCase):
    """Test for the `bam create` command. We run it with --json for easier command
    output parsing.
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_commit(self):
        self.init_repo()
        file_data = b"hello world!\n"

        proj_path = os.path.join(self.path_local_store, self.proj_name)
        co_id = "mysession"
        session_path = os.path.join(proj_path, co_id)

        stdout, stderr = bam_run(["create", co_id], proj_path)
        self.assertEqual("", stderr)

        # check an empty commit fails gracefully
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)
        self.assertEqual("Nothing to commit!\n", stdout)

        # now do a real commit
        file_quick_write(session_path, "testfile.txt", file_data)
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)

    def test_checkout(self):
        self.init_repo()
        file_data = b"hello world!\n"

        proj_path = os.path.join(self.path_local_store, self.proj_name)
        co_id = "mysession"
        session_path = os.path.join(proj_path, co_id)

        stdout, stderr = bam_run(["create", co_id], proj_path)
        self.assertEqual("", stderr)

        # now do a real commit
        file_quick_write(session_path, "testfile.txt", file_data)
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)

        # remove the path
        shutil.rmtree(session_path)

        # checkout the file again
        stdout, stderr = bam_run(["checkout", "testfile.txt"], proj_path)
        self.assertEqual("", stderr)
        # wait_for_input()
        self.assertEqual(True, os.path.exists(os.path.join(proj_path, "testfile/testfile.txt")))

        file_data_test = file_quick_read(os.path.join(proj_path, "testfile/testfile.txt"))
        self.assertEqual(file_data, file_data_test)


class BamBlendTest(BamSessionTestCase):

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    @staticmethod
    def create_blend_id(blendfile, create_id, returncode_test):
        os.makedirs(os.path.dirname(blendfile), exist_ok=True)
        stdout, stderr, returncode = run(
                ("blender",
                 "--background",
                 "--factory-startup",
                 "-noaudio",
                 "--python",
                 os.path.join(CURRENT_DIR, "blendfile_templates.py"),
                 "--",
                 blendfile,
                 create_id,
                 str(returncode_test),
                 ))
        return stdout, stderr, returncode

    def test_create_all(self):
        """ This simply tests all the create functions run without error.
        """
        import blendfile_templates
        returncode_test = 42
        for create_id, create_fn in blendfile_templates.__dict__.items():
            if create_id.startswith("create_"):
                if create_fn.__class__.__name__ == "function":
                    blendfile = os.path.join(TEMP, create_id + ".blend")

                    stdout, stderr, returncode = self.create_blend_id(blendfile, create_id, returncode_test)

                    self.assertEqual(b'', stderr)
                    self.assertEqual(True, os.path.exists(blendfile))
                    self.assertEqual(returncode, returncode_test)
                    with open(blendfile, 'rb') as blendfile_handle:
                        self.assertEqual(b'BLENDER', blendfile_handle.read(7))
                    os.remove(blendfile)

    def test_empty(self):
        blendfile = os.path.join(TEMP, "test.blend")
        returncode_test = 13
        stdout, stderr, returncode = self.create_blend_id(blendfile, "create_blank", returncode_test)
        self.assertEqual(True, os.path.exists(blendfile))
        self.assertEqual(returncode_test, returncode)


class BamDeleteTest(BamSessionTestCase):
    """Test for the `bam commit` command when files are being deleted.
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_delete(self):
        self.init_repo()
        file_data = b"hello world!\n"

        proj_path = os.path.join(self.path_local_store, self.proj_name)
        co_id = "mysession"
        session_path = os.path.join(proj_path, co_id)

        stdout, stderr = bam_run(["create", co_id], proj_path)
        self.assertEqual("", stderr)

        # now do a real commit
        file_quick_write(session_path, "testfile.txt", file_data)
        stdout, stderr = bam_run(["commit", "-m", "tests message"], session_path)
        self.assertEqual("", stderr)

         # remove the path
        shutil.rmtree(session_path)

        # checkout the file again
        stdout, stderr = bam_run(["checkout", "testfile.txt"], proj_path)
        self.assertEqual("", stderr)


        # now delete the file we just checked out
        new_session_path = os.path.join(proj_path, "testfile")
        run(["rm", os.path.join(new_session_path, "testfile.txt")])
        stdout, stderr = bam_run(["commit", "-m", "test deletion"], new_session_path)
        wait_for_input()
        self.assertEqual("", stderr)
        # check if deletion of the file has happened
        d = os.path.join(self.path_local_store, "testfile")

        stdout, stderr = bam_run(["ls", "--json"], d)
        # check for errors in the response
        self.assertEqual("", stderr)

        # parse the response searching for the file. If it fails it means the file has
        # not been removed
        listing = json.loads(stdout)
        print(listing)
        for e in listing:
            self.assertNotEqual(e[0], "testfile.txt")


if __name__ == '__main__':
    data = global_setup()
    unittest.main(exit=False)
    global_teardown(data)

