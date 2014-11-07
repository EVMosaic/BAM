from application import db


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256), unique=True, nullable=False)
    description = db.Column(db.Text)
    value = db.Column(db.String(100), nullable=False)
    data_type = db.Column(db.String(128), nullable=False)

    def __unicode__(self):
        return self.name
