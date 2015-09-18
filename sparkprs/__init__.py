import os
from flask import Flask
from flask.ext.cache import Cache
from werkzeug.contrib.cache import SimpleCache

is_production = os.getenv('SERVER_SOFTWARE', '').startswith('Google App Engine/')
is_test = os.getenv('CI', '') == 'true'
VERSION = os.environ.get('CURRENT_VERSION_ID', 'UNKNOWN_VERSION')

app = Flask('sparkprs', static_folder="../static", template_folder="../templates")


if is_test:
    app.config.from_pyfile('../settings.cfg.template')
elif is_production:
    app.config.from_pyfile('../settings.cfg')
else:
    app.config.from_pyfile('../settings.cfg.local')

if is_test:
    cache = Cache(app, config={'CACHE_TYPE': 'simple'})
else:
    cache = Cache(app, config={'CACHE_TYPE': 'memcached', 'CACHE_KEY_PREFIX': VERSION})
