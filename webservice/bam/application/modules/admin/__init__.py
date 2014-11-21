from application import app, db
#from application import thumb

from flask import render_template, redirect, url_for
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext import admin, login
from flask.ext.admin import Admin, expose
from flask.ext.admin import form
from flask.ext.admin.contrib import sqla
from flask.ext.admin.contrib.sqla import ModelView
from flask.ext.admin.base import BaseView
from flask.ext.security import current_user

from werkzeug import secure_filename
from jinja2 import Markup
from wtforms import fields, validators, widgets
from wtforms.fields import SelectField, TextField
import os, hashlib, time
import os.path as op


def _list_items(view, context, model, name):
    """Utilities to upload and present images
    """
    if not model.name:
        return ''
    return Markup(
        '<div class="select2-container-multi">'
            '<ul class="select2-choices" style="border:0;cursor:default;background:none;">%s</ul></div>' % (
                ''.join(['<li class="select2-search-choice" style="padding:3px 5px;">'
                            '<div>' + item.name + '</div></li>' for item in getattr(model, name)] )))


def _list_thumbnail(view, context, model, name):
    if not getattr(model,name):  # model.name only does not work because name is a string
        return ''
    return ''
    # return Markup('<img src="%s">' % url_for('static',
    #     filename=thumb.thumbnail(getattr(model,name), '50x50', crop='fit')))

# Create directory for file fields to use
file_path = op.join(op.dirname(__file__), '../../static/files',)
try:
    os.mkdir(file_path)
except OSError:
    pass


def prefix_name(obj, file_data):
    # Collect name and extension
    parts = op.splitext(file_data.filename)
    # Get current time (for unique hash)
    timestamp = str(round(time.time()))
    # Has filename only (not extension)
    file_name = secure_filename(timestamp + '%s' % parts[0])
    # Put them together
    full_name = hashlib.md5(file_name).hexdigest() + parts[1]
    return full_name


def image_upload_field(label):
    return form.ImageUploadField(label,
                    base_path=file_path,
                    thumbnail_size=(100, 100, True),
                    namegen=prefix_name,
                    endpoint='filemanager.static')


# Define wtforms widget and field
class CKTextAreaWidget(widgets.TextArea):
    def __call__(self, field, **kwargs):
        kwargs.setdefault('class_', 'ckeditor')
        return super(CKTextAreaWidget, self).__call__(field, **kwargs)


class CKTextAreaField(fields.TextAreaField):
    widget = CKTextAreaWidget()


# Create customized views with access restriction
class CustomModelView(ModelView):
    def is_accessible(self):
        return True
        # return login.current_user.has_role('admin')


class CustomBaseView(BaseView):
    def is_accessible(self):
        return True
        # return login.current_user.has_role('admin')


# Create customized index view class that handles login & registration
class CustomAdminIndexView(admin.AdminIndexView):
    def is_accessible(self):
        return True
        # return login.current_user.has_role('admin')

    @expose('/')
    def index(self):
        return super(CustomAdminIndexView, self).index()

    @expose('/logout/')
    def logout_view(self):
        login.logout_user()
        return redirect(url_for('homepage'))


# Create admin
backend = Admin(
        app,
        "BAM",
        index_view=CustomAdminIndexView(),
        base_template="admin/layout_admin.html"
        )
