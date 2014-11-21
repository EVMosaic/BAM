from application import app
from application import db

from application.modules.projects.model import Project, ProjectSetting

from application.modules.admin import *
from application.modules.admin import _list_thumbnail


class ProjectView(CustomModelView):
    column_searchable_list = ('name',)
    column_list = ('name', 'picture', 'creation_date')
    # column_formatters = { 'picture': _list_thumbnail }
    # form_extra_fields = {'picture': image_upload_field('Header')}
    form_overrides = dict(
        status=SelectField,
        )
    form_args = dict(
        status=dict(
            label='Status',
            choices=[
                ('active', 'Active'),
                ('inactive', 'Inactive'),
                ('canceled', 'Canceled')
            ]),
        )
    inline_models = (
        ProjectSetting,
    )

# Add views
backend.add_view(ProjectView(Project, db.session, name='Projects', url='projects'))
