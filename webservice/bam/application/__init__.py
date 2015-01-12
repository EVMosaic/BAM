#!/usr/bin/env python3
# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****

"""
Environment vars:
- BAM_VERBOSE, set to get debug logging.
"""


# ------------------
# Ensure module path
import os
import sys
path = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if path not in sys.path:
    sys.path.append(path)
del os, sys, path
# --------

import os
import json
import svn.local
import werkzeug
import xml.etree.ElementTree
import logging

from flask import Flask
from flask import jsonify
from flask import abort
from flask import request
from flask import make_response
from flask import url_for
from flask import Response

from flask.views import MethodView
from flask.ext.restful import Api
from flask.ext.httpauth import HTTPBasicAuth
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__)
api = Api(app)
auth = HTTPBasicAuth()

try:
    import config
    app.config.from_object(config.Development)
except ImportError:
    app.config["ALLOWED_EXTENSIONS"] = {'txt', 'mp4', 'png', 'jpg', 'jpeg', 'gif', 'blend', 'zip'}
    app.config["STORAGE_BUNDLES"] = "/tmp/bam_storage_bundles"


db = SQLAlchemy(app)
log = logging.getLogger("webservice")

from application.modules.resources import DirectoryAPI
from application.modules.resources import FileAPI

if os.environ.get("BAM_VERBOSE"):
    logging.basicConfig(level=logging.DEBUG)


@auth.get_password
def get_password(username):
    # Temporarily override API access
    # TODO (fsiddi) check against users table
    return ''
    if username == 'bam':
        return 'bam'
    return None


@auth.error_handler
def unauthorized():
    return make_response(jsonify({'message': 'Unauthorized access'}), 403)
    # return 403 instead of 401 to prevent browsers from displaying
    # the default auth dialog


api.add_resource(DirectoryAPI, '/<project_name>/file_list', endpoint='file_list')
api.add_resource(FileAPI, '/<project_name>/file', endpoint='file')
