from application import app
from application import db

from application.modules.admin.model import Setting
from application.modules.admin import *


# Add views
backend.add_view(CustomModelView(Setting, db.session, name='Settings', url='settings'))
