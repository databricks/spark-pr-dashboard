import site
import os.path
import gae_mini_profiler.profiler
site.addsitedir(os.path.join(os.path.dirname(__file__), 'lib'))


def webapp_add_wsgi_middleware(app):
    app = gae_mini_profiler.profiler.ProfilerWSGIMiddleware(app)
    return app


def gae_mini_profiler_should_profile_production():
    from google.appengine.api import users
    return users.is_current_user_admin()