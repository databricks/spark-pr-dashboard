from flask import render_template

from sparkprs import app
from sparkprs.controllers.tasks import tasks
from sparkprs.controllers.admin import admin
from sparkprs.controllers.login import login
from sparkprs.controllers.jenkins import jenkins
from sparkprs.controllers.prs import prs


app.register_blueprint(login)
app.register_blueprint(jenkins)
app.register_blueprint(prs)
app.register_blueprint(tasks, url_prefix='/tasks')
app.register_blueprint(admin, url_prefix='/admin')


@app.route('/')
@app.route('/open-prs')
@app.route('/users')
@app.route('/users/<username>')
def main(username=None):
    return render_template('index.html')
