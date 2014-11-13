import datetime
from application import db


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    repository_path = db.Column(db.Text, nullable=False)
    upload_path = db.Column(db.Text, nullable=False)
    picture = db.Column(db.String(80))
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)
    status = db.Column(db.String(80)) #active #inactive

    settings = db.relationship('ProjectSetting', backref='project')

    def __str__(self):
        return str(self.name)


class ProjectSetting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer(), db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    value = db.Column(db.String(100), nullable=False)
    data_type = db.Column(db.String(128), nullable=False)

    def __unicode__(self):
        return self.name
