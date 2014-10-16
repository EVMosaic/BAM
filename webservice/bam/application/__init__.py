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

from flask import Flask, jsonify, abort, request, make_response, url_for
from flask.views import MethodView
from flask.ext.restful import Api, Resource, reqparse, fields, marshal
from flask.ext.httpauth import HTTPBasicAuth

app = Flask(__name__)
api = Api(app)
auth = HTTPBasicAuth()

@api.representation('application/octet-stream')
def output_file(data, code, headers=None):
    """Makes a Flask response to return a file."""
    resp = make_response(data, code)
    resp.headers.extend(headers or {})
    return resp

@auth.get_password
def get_password(username):
    if username == 'bam':
        return 'bam'
    return None
 
@auth.error_handler
def unauthorized():
    return make_response(jsonify( { 'message': 'Unauthorized access' } ), 403)
    # return 403 instead of 401 to prevent browsers from displaying 
    # the default auth dialog


class FilesListAPI(Resource):
    """Displays list of files."""
    decorators = [auth.login_required]

    def __init__(self):
        super(FilesListAPI, self).__init__()
        
    def get(self):
        return { 'message': 'Display files list' }


class FileAPI(Resource):
    """Downloads a file."""

    decorators = [auth.login_required]
    def __init__(self):
        # self.reqparse = reqparse.RequestParser()
        # self.reqparse.add_argument('path', 
        #     type = str, 
        #     location = 'json')
        super(FileAPI, self).__init__()

    def get(self, path):
        with open(path, 'r') as f:
            body = f.read()
        return output_file(body, 200)
        #return { 'path': path }


api.add_resource(FilesListAPI, '/files', endpoint = 'files')
api.add_resource(FileAPI, '/file/<path:path>', endpoint = 'file')
