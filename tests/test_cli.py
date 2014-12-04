#!/usr/bin/env python3
# Apache License, Version 2.0

"""
Test bam command line client

Run all tests:

   python3 test_cli.py

Run a single test:

   python3 -m unittest test_cli.BamCommitTest.test_checkout
"""

import os
VERBOSE = os.environ.get("VERBOSE", False)
if VERBOSE == "0":
    VERBOSE = None
if VERBOSE:
    # for the server subprocess
    os.environ["BAM_VERBOSE"] = "1"


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


# -------------------------
# Quiet the werkzeug logger
if not VERBOSE:
    import werkzeug
    import werkzeug._internal
    werkzeug._internal._log = lambda *a, **b: None
    del werkzeug
# --------


# -----------------------------------------
# Ensure we get stdout & stderr on sys.exit
#
# We have this because we override the standard output,
# _AND_ during this state a command may call `sys.exit`
# In this case, we the output is hidden which is very annoying.
#
# So override `sys.exit` with one that prints to the original
# stdout/stderr on exit.
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
#
# Argparse can call `sys.exit` if the wrong args are given.
# This messes with testing, which we want to keep the process running.
#
# This monkey-patches in an exist function which simply raises an exception.
# We could do something a bit nicer here,
# but for now just use a basic exception.
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

TEMP_LOCAL = "/tmp/bam_test"
# Separate tmp folder for server, since we don't reset the server at every test
TEMP_SERVER = "/tmp/bam_test_server"
PORT = 5555
PROJECT_NAME = "test_project"

# running scripts next to this one!
CURRENT_DIR = os.path.dirname(__file__)


def args_as_string(args):
    """ Print args so we can paste them to run them again.
    """
    import shlex
    return " ".join([shlex.quote(c) for c in args])


def run(cmd, cwd=None):
    if VERBOSE:
        print(">>> ", args_as_string(cmd))
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
        print(">>> ", args_as_string(cmd))
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
            import shlex
            sys.stdout.write("bam %s\n" % " ".join([shlex.quote(c) for c in argv]))

            # input('press_key!:')

        with StdIO() as fakeio:
            bam.main(argv)
            ret = fakeio.read()

        if VERBOSE:
            sys.stdout.write("   stdout:  %s\n" % ret[0].strip())
            sys.stdout.write("   stderr:  %s\n" % ret[1].strip())

    return ret


def bam_run_as_json(argv, cwd=None):
    stdout, stderr = bam_run(argv, cwd=cwd)
    if stderr:
        raise Exception(stderr)
        return None

    ret = None

    import json
    try:
        ret = json.loads(stdout)
    except Exception as e:
        print("---- JSON BEGIN (invalid) ----")
        print(stdout)
        print("---- JSON END ----")
        raise e
    return ret


def file_quick_write(path, filepart=None, data=None, append=False):
    """Quick file creation utility.
    """
    if data is None:
        data = b''

    mode = 'a' if append else 'w'
    if type(data) is bytes:
        mode = mode + 'b'
    elif type(data) is str:
        pass
    else:
        raise Exception("type %r not known" % type(data))

    if filepart is not None:
        path = os.path.join(path, filepart)

    os.makedirs(os.path.dirname(path), exist_ok=True)
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


def file_quick_touch_blend(path, filepart=None, times=None):
    if filepart is not None:
        path = os.path.join(path, filepart)

    if not os.path.exists(path):
        Exception("Path not found %r" % path)

    # we can write junk data into the end of the blend file
    with open(path, 'a') as fh:
        fh.write("_")
    os.utime(path, times)


def file_quick_image(path, filepart=None):
    def write_png(buf, width, height):
        """ buf: must be bytes or a bytearray in py3, a regular string in py2. formatted RGBARGBA... """
        import zlib
        import struct

        width_byte_4 = width * 4
        raw_data = b''.join(b'\x00' + buf[span:span + width_byte_4]
                            for span in range((height - 1) * width * 4, -1, - width_byte_4))

        def png_pack(png_tag, data):
            chunk_head = png_tag + data
            return (struct.pack("!I", len(data)) +
                    chunk_head +
                    struct.pack("!I", 0xFFFFFFFF & zlib.crc32(chunk_head)))

        return b''.join([
            b'\x89PNG\r\n\x1a\n',
            png_pack(b'IHDR', struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)),
            png_pack(b'IDAT', zlib.compress(raw_data, 9)),
            png_pack(b'IEND', b'')])

    if filepart is not None:
        path = os.path.join(path, filepart)
    with open(path, 'wb') as f:
        f.write(write_png(b'0000' * 4, 2, 2))


def _dbg_dump_path(path):
    stdout, stderr, returncode = run(["find", path], path)
    print("Contents of: %r" % path)
    print("\n".join(sorted(stdout.decode('utf-8').split("\n"))))


def blendfile_template_create(blendfile, blendfile_root, create_id, create_data, deps):
    returncode_test = 123
    blendfile_deps_json = os.path.join(TEMP_LOCAL, "blend_template_deps.json")
    os.makedirs(os.path.dirname(blendfile), exist_ok=True)

    if create_data is not None:
        blendfile_create_data_json = os.path.join(TEMP_LOCAL, "blendfile_create_data.json")
        with open(blendfile_create_data_json, 'w') as f:
            import json
            json.dump(
                    create_data, f, ensure_ascii=False,
                    check_circular=False,
                    # optional (pretty)
                    sort_keys=True, indent=4, separators=(',', ': '),
                    )
            del json
    else:
        blendfile_create_data_json = None

    blender = os.getenv('BLENDER_BIN', "blender")
    cmd = (
        blender,
        "--background",
        "--factory-startup",
        "-noaudio",
        "--python",
        os.path.join(CURRENT_DIR, "blendfile_templates.py"),
        "--",
        blendfile,
        blendfile_root,
        blendfile_deps_json,
        create_id,
        "NONE" if blendfile_create_data_json is None else blendfile_create_data_json,
        str(returncode_test),
        )
    stdout, stderr, returncode = run(cmd)

    if os.path.exists(blendfile_deps_json):
        with open(blendfile_deps_json, 'r') as f:
            import json
            deps[:] = json.load(f)
            del json
        os.remove(blendfile_deps_json)
    else:
        deps.clear()

    if blendfile_create_data_json is not None:
        os.remove(blendfile_create_data_json)

    if returncode != returncode_test:
        # verbose will have already printed
        if not VERBOSE:
            print(">>> ", args_as_string(cmd))
            sys.stdout.write("   stdout:  %s\n" % stdout.strip())
            sys.stdout.write("   stderr:  %s\n" % stderr.strip())
            sys.stdout.write("   return:  %d\n" % returncode)
        return False
    else:
        return True


def blendfile_template_create_from_files(proj_path, session_path, blendfile_pair, images):

    for f_proj, f_local in images:
        f_abs = os.path.join(session_path, f_proj)
        os.makedirs(os.path.dirname(f_abs))
        file_quick_image(f_abs)

    blendfile_abs = os.path.join(session_path, blendfile_pair[0])
    deps = []
    if not blendfile_template_create(blendfile_abs, session_path, "create_from_files", None, deps):
        return False

    # not essential but we need to be sure what we made has correct deps
    # otherwise further tests will fail
    ret = bam_run_as_json(["deps", blendfile_abs, "--json"], proj_path)

    # not real test since we don't use static method,
    # just check we at least account for all deps
    assert(len(ret) == len(images))


def blendfile_template_create_from_file_liblinks(proj_path, session_path, blendfile, links):

    blendfile_abs = os.path.join(session_path, blendfile)
    deps = []

    links_abs = []
    for f, f_id, f_links in links:
        f_abs = os.path.join(session_path, f)
        f_abs_dir = os.path.dirname(f_abs)
        os.makedirs(f_abs_dir, exist_ok=True)
        links_abs.append((
                f_abs,
                f_id,
                [os.path.join(session_path, l) for l in f_links],
                ))

    if not blendfile_template_create(blendfile_abs, session_path, "create_from_file_liblinks", links_abs, deps):
        return False

    # not essential but we need to be sure what we made has correct deps
    # otherwise further tests will fail
    ret = bam_run_as_json(["deps", blendfile_abs, "--json"], proj_path)

    # not real test since we don't use static method,
    # just check we at least account for all deps
    # assert(len(ret) == len(links))
    return True


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
                repository_path=os.path.join(TEMP_LOCAL, "remote_store/svn_checkout"),
                upload_path=os.path.join(TEMP_LOCAL, "remote_store/upload"),
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


def global_setup(use_server=True):
    data = []

    if VERBOSE:
        # for server
        import logging
        logging.basicConfig(level=logging.DEBUG)
        del logging

    shutil.rmtree(TEMP_SERVER, ignore_errors=True)
    shutil.rmtree(TEMP_LOCAL, ignore_errors=True)

    if use_server:
        p = server()
        data.append(p)

    return data


def global_teardown(data, use_server=True):

    if use_server:
        p = data.pop(0)
        p.terminate()

    shutil.rmtree(TEMP_SERVER, ignore_errors=True)
    shutil.rmtree(TEMP_LOCAL, ignore_errors=True)


# ------------------------------------------------------------------------------
# Unit Tests

import unittest


class BamSimpleTestCase(unittest.TestCase):
    """ Basic testcase, only make temp dirs.
    """
    def setUp(self):

        # for running single tests
        if __name__ != "__main__":
            self._data = global_setup(use_server=False)

        if not os.path.isdir(TEMP_LOCAL):
            os.makedirs(TEMP_LOCAL)

    def tearDown(self):
        # input('Wait:')
        shutil.rmtree(TEMP_LOCAL)

        # for running single tests
        if __name__ != "__main__":
            global_teardown(self._data, use_server=False)


class BamSessionTestCase(unittest.TestCase):

    def setUp(self):

        # for running single tests
        if __name__ != "__main__":
            self._data = global_setup()

        if not os.path.isdir(TEMP_LOCAL):
            os.makedirs(TEMP_LOCAL)
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
        shutil.rmtree(TEMP_LOCAL)

        # for running single tests
        if __name__ != "__main__":
            global_teardown(self._data)

    def get_url(self):
        url_full = "%s@%s/%s" % (self.user_name, self.server_addr, self.proj_name)
        user_name, url = url_full.rpartition('@')[0::2]
        return url_full, user_name, url

    def init_defaults(self):
        self.path_local_store = os.path.join(TEMP_LOCAL, "local_store")
        self.path_remote_store = os.path.join(TEMP_LOCAL, "remote_store")

        self.proj_name = PROJECT_NAME
        self.user_name = "user"
        self.server_addr = "http://localhost:%s" % PORT

    def init_repo(self):
        url_full, user_name, url = self.get_url()
        stdout, stderr = bam_run(["init", url_full], self.path_local_store)
        self.assertEqual("", stderr)
        proj_path = os.path.join(self.path_local_store, self.proj_name)
        return proj_path

    def init_session(self, session_name):
        """ Initialize the project and create a new session.
        """

        proj_path = self.init_repo()
        session_path = os.path.join(proj_path, session_name)

        stdout, stderr = bam_run(["create", session_name], proj_path)
        self.assertEqual("", stderr)
        return proj_path, session_path


class BamInitTest(BamSessionTestCase):
    """Test the `bam init user@http://bamserver/projectname` command.
    We verify that a project folder is created, and that it contains a .bam subfolder
    with a config file, with the right url and user values (given in the command)
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_init(self):
        proj_path = self.init_repo()

        url_full, user_name, url = self.get_url()
        with open(os.path.join(proj_path, ".bam", "config")) as f:
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
        proj_path = self.init_repo()

        ret = bam_run_as_json(["ls", "--json"], proj_path)

        self.assertEqual(2, len(ret))


class BamCommitTest(BamSessionTestCase):
    """Test for the `bam create` command. We run it with --json for easier command
    output parsing.
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_commit(self):
        session_name = "mysession"
        file_name = "testfile.txt"
        file_data = b"hello world!\n"

        proj_path, session_path = self.init_session(session_name)

        # check an empty commit fails gracefully
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)
        self.assertEqual("Nothing to commit!\n", stdout)

        # now do a real commit
        file_quick_write(session_path, file_name, file_data)
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)

    def test_commit_partial(self):
        """Checks the commit is only writing the modified files,
        across multiple commits and changes.
        """
        session_name = "mysession"
        files = (
            "a.data",
            os.path.join("b_dir", "b.data"),
            os.path.join("c_dir", "c_subdir", "c.data"),
            os.path.join("d_dir", "d_subdir", "d_nested", "d.data"),
            )
        proj_path, session_path = self.init_session(session_name)

        # ------
        # Commit
        # arbitrary data so this is seen as binary data
        file_binary_chunk = b'\x89'
        for f in files:
            file_quick_write(session_path, f, file_binary_chunk + f.encode('ascii'))

        stdout, stderr = bam_run(["commit", "-m", "test 1"], session_path)
        self.assertEqual("", stderr)

        # now check that status reads there are no changes
        ret = bam_run_as_json(["status", "--json"], session_path)
        self.assertEqual([], ret)

        # ------
        # Modify
        # check the status now shows modified
        for f in files:
            file_quick_write(session_path, f, b'_foo', append=True)

        ret = bam_run_as_json(["status", "--json"], session_path)
        ret.sort()
        self.assertEqual(
                [["M", "a.data"],
                 ["M", "b_dir/b.data"],
                 ["M", "c_dir/c_subdir/c.data"],
                 ["M", "d_dir/d_subdir/d_nested/d.data"],
                 ], ret)

class BamCheckoutTest(BamSessionTestCase):
    """Test for the `bam checkout` command.
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_checkout(self):
        session_name = "mysession"
        file_name = "other_file.txt"
        file_data = b"yo world!\n"

        proj_path, session_path = self.init_session(session_name)

        # now do a real commit
        file_quick_write(session_path, file_name, file_data)
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)

        # remove the path
        shutil.rmtree(session_path)

        # checkout the file again
        stdout, stderr = bam_run(["checkout", file_name, "--output", session_path], proj_path)
        self.assertEqual("", stderr)
        # wait_for_input()
        self.assertTrue(os.path.exists(os.path.join(session_path, file_name)))

        file_data_test = file_quick_read(os.path.join(session_path, file_name))
        self.assertEqual(file_data, file_data_test)

    def test_update_blank(self):
        session_name = "mysession"
        proj_path, session_path = self.init_session(session_name)
        stdout, stderr = bam_run(["update"], session_path)
        # Empty and new session should not update at all
        self.assertEqual("", stderr)
        self.assertEqual("Nothing to update!\n", stdout)

        #stdout, stderr = bam_run(["checkout"], session_path)




class BamBlendTest(BamSimpleTestCase):

    def test_create_all(self):
        """ This simply tests all the create functions run without error.
        """
        import blendfile_templates
        TEMP_SESSION = os.path.join(TEMP_LOCAL, "blend_file_template")

        def iter_files_session():
            for dirpath, dirnames, filenames in os.walk(TEMP_SESSION):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    yield filepath

        for create_id, create_fn in blendfile_templates.__dict__.items():
            if (create_id.startswith("create_") and create_fn.__class__.__name__ == "function"):

                # ignore create functions which need data
                if create_id in {"create_from_file_liblinks"}:
                    continue

                os.makedirs(TEMP_SESSION)

                blendfile = os.path.join(TEMP_SESSION, create_id + ".blend")
                deps = []

                if not blendfile_template_create(blendfile, TEMP_SESSION, create_id, None, deps):
                    # self.fail("blend file couldn't be create")
                    # ... we want to keep running
                    self.assertTrue(False, True)  # GRR, a better way?
                    shutil.rmtree(TEMP_SESSION)
                    continue

                self.assertTrue(os.path.exists(blendfile))
                with open(blendfile, 'rb') as blendfile_handle:
                    self.assertEqual(b'BLENDER', blendfile_handle.read(7))
                os.remove(blendfile)

                # check all deps are accounted for
                for f in deps:
                    self.assertTrue(os.path.exists(f))
                for f in iter_files_session():
                    self.assertIn(f, deps)

                shutil.rmtree(TEMP_SESSION)

    def test_empty(self):
        file_name = "testfile.blend"
        blendfile = os.path.join(TEMP_LOCAL, file_name)
        if not blendfile_template_create(blendfile, TEMP_LOCAL, "create_blank", None, []):
            self.fail("blend file couldn't be created")
            return

        self.assertTrue(os.path.exists(blendfile))


class BamDeleteTest(BamSessionTestCase):
    """Test for the `bam commit` command when files are being deleted.
    """

    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_delete(self):
        session_name = "mysession"
        file_name = "testfile.blend"
        proj_path, session_path = self.init_session(session_name)

        # now do a real commit
        blendfile = os.path.join(session_path, file_name)
        if not blendfile_template_create(blendfile, session_path, "create_blank", None, []):
            self.fail("blend file couldn't be created")
            return

        stdout, stderr = bam_run(["commit", "-m", "tests message"], session_path)
        self.assertEqual("", stderr)

        # remove the path
        shutil.rmtree(session_path)
        del session_path

        # -----------
        # New Session

        # checkout the file again
        stdout, stderr = bam_run(["checkout", file_name, "--output", "new_out"], proj_path)
        self.assertEqual("", stderr)

        # now delete the file we just checked out
        session_path = os.path.join(proj_path, "new_out")
        os.remove(os.path.join(session_path, file_name))
        stdout, stderr = bam_run(["commit", "-m", "test deletion"], session_path)
        self.assertEqual("", stderr)
        # check if deletion of the file has happened

        listing = bam_run_as_json(["ls", "--json"], session_path)

        # parse the response searching for the file. If it fails it means the file has
        # not been removed
        for e in listing:
            self.assertNotEqual(e[0], file_name)


class BamRelativeAbsoluteTest(BamSessionTestCase):
    """Create a checkout and commit it into the repository,
    using both absolute & relative paths.
    """
    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def helper_test_from_files(self, blendfile_pair, images):
        """
        """
        session_name = "mysession"
        proj_path, session_path = self.init_session(session_name)

        # create the image files we need
        blendfile_template_create_from_files(proj_path, session_path, blendfile_pair, images)

        # now commit the files
        stdout, stderr = bam_run(["commit", "-m", "commit shot_01"], session_path)
        self.assertEqual("", stderr)

        # remove the path
        shutil.rmtree(session_path)
        del session_path

        # -----------
        # New Session

        # checkout the file again
        stdout, stderr = bam_run(["checkout", blendfile_pair[0], "--output", "new_out"], proj_path)
        self.assertEqual("", stderr)

        # now delete the file we just checked out
        session_path = os.path.join(proj_path, "new_out")
        # _dbg_dump_path(session_path)

        # Now check if all the paths we expected are found!
        for f_proj, f_local in images:
            f_abs = os.path.join(session_path, f_local)
            # assert message isn't so useful
            if VERBOSE:
                print("Exists?", f_abs)
            self.assertTrue(os.path.exists(f_abs))

    def helper_test_from_liblinks(self, blendfile, liblinks_src, liblinks_dst):
        session_name = "mysession"
        proj_path, session_path = self.init_session(session_name)

        # create the image files we need
        blendfile_template_create_from_file_liblinks(proj_path, session_path, blendfile, liblinks_src)

        # now commit the files
        stdout, stderr = bam_run(["commit", "-m", "commit shot_01"], session_path)
        self.assertEqual("", stderr)

        # remove the path
        shutil.rmtree(session_path)
        del session_path

        # -----------
        # New Session

        # checkout the file again
        stdout, stderr = bam_run(["checkout", blendfile, "--output", "new_out"], proj_path)
        self.assertEqual("", stderr)

        # now delete the file we just checked out
        session_path = os.path.join(proj_path, "new_out")

        # _dbg_dump_path(session_path)

        # Now check if all the paths we expected are found!
        for f_rel in liblinks_dst:
            f_abs = os.path.join(session_path, f_rel)
            # assert message isn't so useful
            if VERBOSE:
                print("Exists?", f_abs)
            self.assertTrue(os.path.exists(f_abs))
        return proj_path, session_path

    def test_absolute_relative_images(self):
        """
        Layout is as follows.

         - ./shots/01/shot_01.blend
         - ./shots/01/maps/special.png
         - ./maps/generic.png

        Maps to...
         - ./shot_01.blend
         - ./_maps/special.png
         - ./maps/generic.png
        """

        # absolute path: (project relative) -->
        # checkout path: (relative to blend)
        blendfile_pair = ("shots/01/shot_01.blend", "shot_01.blend")
        if 1:
            images = (
                ("shots/01/maps/special.png", "maps/special.png"),
                ("maps/generic.png", "_maps/generic.png"),
                )
        else:
            images = (
                ("shots/01/maps/special.png", "maps/special.png"),
                ("maps/generic.png", "__/__/maps/generic.png"),
                )

        self.helper_test_from_files(blendfile_pair, images)

    def test_absolute_relative_liblinks(self):
        """
        Layout is as follows.

         - ./shots/01/shot_01.blend
         - ./shots/01/maps/special.blend
         - ./maps/generic.blend

        Maps to...
         - ./shot_01.blend
         - ./maps/special.blend
         - ./_maps/generic.blend
        """
        # NOTE: test_absolute_relative_from_subdir() test calls this one.
        blendfile = "shots/01/shot_01.blend"

        blend_shot = "shots/01/shot_01.blend"
        blend_special = "shots/01/maps/special.blend"
        blend_generic = "maps/generic.blend"

        # absolute path: (project relative) -->
        # checkout path: (relative to blend)
        liblinks_src = (
            (blend_shot, "Scene10", (blend_special,)),
            (blend_special, "MySpecial", (blend_generic,)),
            (blend_generic, "MyGeneric", ()),
            )
        liblinks_dst = (
            "shot_01.blend",
            "maps/special.blend",
            "_maps/generic.blend",
            )

        return self.helper_test_from_liblinks(blendfile, liblinks_src, liblinks_dst)

    def test_absolute_relative_from_subdir(self):
        """
        Layout is as follows.

         - ./shots/01/shot_01.blend
         - ./shots/01/maps/special.blend
         - ./maps/generic.blend

        Maps to...
         - ./shot_01.blend
         - ./_maps/special.blend
         - ./maps/generic.blend

        Now add a file to these directory,
        - ./maps_more/rel.txt
        - ./_maps_more/abs.txt

        Maps to...
        - ./shots/01/maps_more/rel.txt
        - ./maps_more/abs.txt
        """

        # WEAK, set in the test called next
        blendfile = "shots/01/shot_01.blend"
        proj_path, session_path = self.test_absolute_relative_liblinks()

        shutil.rmtree(session_path)

        stdout, stderr = bam_run(["checkout", blendfile, "--output", "new_out"], proj_path)
        self.assertEqual("", stderr)

        session_path = os.path.join(proj_path, "new_out")

        # create these new
        file_quick_write(session_path, os.path.join("maps_more", "rel.txt"))
        file_quick_write(session_path, os.path.join("_maps_more", "abs.txt"))

        stdout, stderr = bam_run(["commit", "-m", "new abs and rel files"], session_path)
        self.assertEqual("", stderr)

        ret = bam_run_as_json(["ls", "--json"], proj_path)

        ret = bam_run_as_json(["ls", "shots/01/maps_more", "--json"], proj_path)
        self.assertIn(["rel.txt", "file"], ret)

        ret = bam_run_as_json(["ls", "maps_more", "--json"], proj_path)
        self.assertIn(["abs.txt", "file"], ret)

    def _test_absolute_relative_from_blendfiles__structure(self, proj_path, session_path):
        # used by both
        # - test_absolute_relative_from_blendfiles()
        # - test_absolute_relative_from_blendfiles_partial()
        #
        shutil.rmtree(session_path)

        blendfile = os.path.join("subdir", "house_lib_user.blend")

        # ---- make a new checkout

        def _check():
            ret = bam_run_as_json(["deps", os.path.join(session_path, os.path.basename(blendfile)), "--json"], proj_path)
            ret.sort()

            self.assertEqual(ret[0][1], "//" + os.path.join("_abs", "path", "house_abs.blend"))
            self.assertEqual(ret[0][3], "OK")
            self.assertEqual(ret[1][1], "//" + os.path.join("rel", "path", "house_rel.blend"))
            self.assertEqual(ret[1][3], "OK")

        stdout, stderr = bam_run(["checkout", blendfile, "--output", session_path], proj_path)
        self.assertEqual("", stderr)
        _check()

        # ---- touch and commit

        file_quick_touch_blend(os.path.join(os.path.join(session_path, "_abs", "path", "house_abs.blend")))
        file_quick_touch_blend(os.path.join(os.path.join(session_path, "rel", "path", "house_rel.blend")))
        file_quick_touch_blend(os.path.join(os.path.join(session_path, os.path.basename(blendfile))))

        stdout, stderr = bam_run(["commit", "-m", "just touched"], session_path)
        self.assertEqual("", stderr)

        shutil.rmtree(session_path)

        stdout, stderr = bam_run(["checkout", blendfile, "--output", session_path], proj_path)
        self.assertEqual("", stderr)
        _check()
        # _dbg_dump_path(session_path)

    def test_absolute_relative_from_blendfiles(self):
        """
        This uses 3x blend files to test multi-level commit, checkout.

         - ./subdir/house_lib_user.blend
         - ./subdir/rel/path/house_rel.blend
         - ./abs/path/house_abs.blend

        Maps to...
         - ./house_lib_user.blend
         - ./rel/path/house_rel.blend
         - ./_abs/path/house_abs.blend
        """

        session_name = "mysession"
        proj_path, session_path = self.init_session(session_name)

        if 1:
            import shutil
            for d in ("abs", "subdir"):
                # path cant already exist, ugh
                shutil.copytree(
                        os.path.join(CURRENT_DIR, "blends", "multi_level", d),
                        os.path.join(session_path, d),
                        )
            stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
            self.assertEqual("", stderr)

        self._test_absolute_relative_from_blendfiles__structure(proj_path, session_path)

    def test_absolute_relative_from_blendfiles_partial(self):
        """Same as test_absolute_relative_from_blendfiles(),
        but start from a single file commit
        """
        import shutil

        session_name = "mysession"
        proj_path, session_path = self.init_session(session_name)

        blendfile = os.path.join("subdir", "house_lib_user.blend")
        blendfile_abs = os.path.join(session_path, blendfile)

        # --------------------------------------------------------------------
        # now do the same test, on a checkout which already _has_ 'subdir/house_lib_user.blend'
        # to begin with, then add in the linked libs afterwards.

        if not blendfile_template_create(blendfile_abs, session_path, "create_blank", None, []):
            self.fail("blend file couldn't be created")
            return
        self.assertTrue(os.path.exists(blendfile_abs))

        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)

        shutil.rmtree(session_path)

        stdout, stderr = bam_run(["checkout", blendfile, "--output", session_path], proj_path)
        self.assertEqual("", stderr)

        # Now write the relative paths into the current checkout,
        # they must now map back to the correct paths.

        if 1:
            import shutil
            shutil.copytree(
                    os.path.join(CURRENT_DIR, "blends", "multi_level", "abs", "path"),
                    os.path.join(session_path, "_abs", "path"),
                    )
            shutil.copytree(
                    os.path.join(CURRENT_DIR, "blends", "multi_level", "subdir", "rel", "path"),
                    os.path.join(session_path, "rel", "path"),
                    )
        shutil.copy(
                os.path.join(CURRENT_DIR, "blends", "multi_level", "subdir", os.path.basename(blendfile)),
                session_path,
                )

        # Now store the link as if we made the path locally, manually adding "./_abs/"
        # This test is to show that BAM can remap this back to an absolute dir.
        #
        # XXX, binary search & replace, WEAK!
        with open(os.path.join(session_path, os.path.basename(blendfile)), 'rb') as f:
            data = f.read()
        data = data.replace(
                b'//../abs/path/house_abs.blend\x00',
                b'//_abs/path/house_abs.blend\x00__',
                1)
        with open(os.path.join(session_path, os.path.basename(blendfile)), 'wb') as f:
            f.write(data)
        del data, f
        # XXX (end hack!)

        stdout, stderr = bam_run(["commit", "-m", "new house to remap"], session_path)
        self.assertEqual("", stderr)

        self._test_absolute_relative_from_blendfiles__structure(proj_path, session_path)

        # ret = bam_run_as_json(["ls", "abs/path", "--json"], proj_path)
        # self.assertEqual(ret[0], ["house_abs.blend", "file"])
        # ret = bam_run_as_json(["ls", "subdir/rel/path", "--json"], proj_path)
        # self.assertEqual(ret[0], ["house_rel.blend", "file"])


class BamIgnoreTest(BamSessionTestCase):
    """Checks out a project, creates a .bamignore file with a few rules
    and tries to commit files that violate them.
    """
    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_ignore(self):
        session_name = "mysession"
        file_name = "testfile.txt"
        file_data = b"hello world!\n"

        # Regular expressions for smart people
        file_data_bamignore = (
            r".*\.txt$",
            r".*/subfolder/.*",
            )

        proj_path, session_path = self.init_session(session_name)

        # write the .bamignore in the session root
        file_quick_write(proj_path, ".bamignore", "\n".join(file_data_bamignore))

        # create some files
        file_quick_write(session_path, file_name, file_data)

        import os
        subdir_path = os.path.join(session_path, "subfolder")
        os.makedirs(subdir_path)
        file_quick_write(subdir_path, "testfile.blend1", file_data)

        # now check for status
        stdout, stderr = bam_run(["status", ], session_path)
        self.assertEqual("", stderr)

        # try to commit
        stdout, stderr = bam_run(["commit", "-m", "test message"], session_path)
        self.assertEqual("", stderr)
        self.assertEqual("Nothing to commit!\n", stdout)

    def test_invalid_ignore(self):
        session_name = "mysession"
        file_name = "testfile.txt"
        file_data = b"hello world!\n"

        # A failing regex that breaks syntax highlight as nice side effect
        file_data_bamignore = (
            r".*\.txt$",
            r".*\.($",  # invalid!
            )

        proj_path, session_path = self.init_session(session_name)

        # write the .bamignore in the session root
        file_quick_write(proj_path, ".bamignore", "\n".join(file_data_bamignore))

        # create some files
        file_quick_write(session_path, file_name, file_data)

        # now check for status
        self.assertRaises(RuntimeError, bam_run, ["status", ], session_path)


if __name__ == '__main__':
    data = global_setup()
    unittest.main(exit=False)
    global_teardown(data)
