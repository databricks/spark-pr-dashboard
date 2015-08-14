import os
from flask import Flask
from flask.ext.cache import Cache

is_production = os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/')
VERSION = os.environ.get('CURRENT_VERSION_ID', 'UNKNOWN_VERSION')

app = Flask('sparkprs', static_folder="../static", template_folder="../templates")

if is_production:
    app.config.from_pyfile('../settings.cfg')
else:
    app.config.from_pyfile('../settings.cfg.local')

cache = Cache(app, config={'CACHE_TYPE': 'memcached', 'CACHE_KEY_PREFIX': VERSION})
