import datetime
from application import db


class Bundle(db.Model):
    """Bundles are the results of a 'bam bundle' command. When running such command
    for the first time we:
        - create a task in the queue (see the queue module)
        - create a bundle entry and set its status as 'waiting'
        - executed the task (at due time)
        - set the bundle entry status to 'building'
        - once completed we set the status to 'available'
        - serve the bundle_path

    The bundle_path can be used but an application that shares access to the BAM
    storage, as well as by the 'bam checkout' command itself (later on).

    If this is not the case, we will provide a working download link via the 'bam info'.
    """
    id = db.Column(db.Integer, primary_key=True)
    source_file_path = db.Column(db.String(512), nullable=False)
    bundle_path = db.Column(db.String(512))
    status = db.Column(db.String(80))
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)
    update_date = db.Column(db.DateTime(), default=datetime.datetime.now)

    def __str__(self):
        return str(self.name)
