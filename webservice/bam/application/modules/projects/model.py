import datetime
from application import db

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    repository_path = db.Column(db.Text, nullable=False)
    upload_path = db.Column(db.Text, nullable=False)
    picture = db.Column(db.String(80))
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)
    status = db.Column(db.String(80)) #pending #active #inactive

    def __str__(self):
        return str(self.name)
