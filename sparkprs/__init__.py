import os
from flask import Flask

app = Flask('sparkprs', static_folder="../static", template_folder="../templates")
app.config.from_pyfile('../settings.cfg')

VERSION = os.environ['CURRENT_VERSION_ID']