#!/usr/bin/env python3

"""
Welcome to the webservice test suite. Simply run python test_webservice.py and check
that all tests pass.

Individual tests can be run with the following syntax:

    python tests.py ServerTestCase.test_job_delete

"""

import os
import sys
from base64 import b64encode
from werkzeug import Headers

# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webservice", "bam"))
if path not in sys.path:
    sys.path.append(path)
del path

TMP_DIR = "/tmp/bam_webservice_test"
PROJECT_NAME = "mytestproject"

from application import app
from application import db

from test_cli import svn_repo_create
from test_cli import svn_repo_checkout
from test_cli import file_quick_touch
from test_cli import run_check
from test_cli import wait_for_input

from application.modules.projects.model import Project
from application.modules.projects.model import ProjectSetting

import unittest
import tempfile
import json
import shutil


class ServerTestingUtils:

    def add_project(self, is_active=True):
        project = Project(
            name='Caminandes')
        db.session.add(project)
        db.session.commit()

        if is_active:
            setting = Setting(
                name='active_project',
                value=str(project.id))
            db.session.add(setting)
            db.session.commit()
        return project.id


class ServerTestCase(unittest.TestCase):

    utils = ServerTestingUtils()

    def setUp(self):

        if not os.path.isdir(TMP_DIR):
            os.makedirs(TMP_DIR)

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

        dummy_file = os.path.join(path_svn_checkout, "file1")
        file_quick_touch(dummy_file)

        # adds all files recursively
        if not run_check(["svn", "add", dummy_file]):
            return False

        if not run_check(["svn", "commit", "-m", "First commit"], path_svn_checkout):
            return False


        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+ TMP_DIR +'/test.sqlite'
        app.config['TESTING'] = True
        db.create_all()
        # Create a testing project, based on the global configuration (depends on a
        # correct initialization of the SVN repo and on the creation of a checkout)

        # TODO(fsiddi): turn these values in variables
        project = Project(
            name=PROJECT_NAME,
            repository_path=os.path.join(TMP_DIR, "remote_store/svn_checkout"),
            upload_path=os.path.join(TMP_DIR, "remote_store/upload"),
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
        self.app = app.test_client()

    def tearDown(self):
        shutil.rmtree(TMP_DIR)

    def init_defaults(self):
        self.path_remote_store = os.path.join(TMP_DIR, "remote_store")
        self.proj_name = PROJECT_NAME


    def open_with_auth(self, url, method, data=None):
        a = b64encode(b"username:").decode('ascii')

        if method == 'GET':
            args = ['?',]
            for k, v in data.items():
                args.append(k + '=' + v + '&')
            url = url + ''.join(args)

        return self.app.open(url,
            method=method,
            headers={
                'Authorization': 'Basic ' + str(a)
            },
            data=data,
        )


class ServerUsageTest(ServerTestCase):
    def __init__(self, *args):
        self.init_defaults()
        super().__init__(*args)

    def test_directory_browse(self):
        res = self.open_with_auth('/{0}/file_list'.format(PROJECT_NAME), 
            'GET', 
            data=dict(path=''))

        assert res.status_code == 200
        d = json.loads(res.data.decode('utf-8'))
        # print(d)


    def test_file_info(self):
        res = self.open_with_auth('/{0}/file'.format(PROJECT_NAME), 
            'GET', 
            data=dict(filepath='file1', command='info'))

        assert res.status_code == 200
        f = json.loads(res.data.decode('utf-8'))
        # print(f['size'])


    def test_file_bundle(self):
        res = self.open_with_auth('/{0}/file'.format(PROJECT_NAME), 
            'GET', 
            data=dict(filepath='file1', command='bundle'))

        assert res.status_code == 200
        f = json.loads(res.data.decode('utf-8'))
        print(f['filepath'])


if __name__ == '__main__':
    unittest.main()
