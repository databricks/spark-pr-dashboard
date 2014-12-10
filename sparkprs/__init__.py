import os
from flask import Flask
from flask.ext.cache import Cache

app = Flask('sparkprs', static_folder="../static", template_folder="../templates")
app.config.from_pyfile('../settings.cfg')

VERSION = os.environ['CURRENT_VERSION_ID']

cache = Cache(app, config={'CACHE_TYPE': 'memcached', 'CACHE_KEY_PREFIX': VERSION})
