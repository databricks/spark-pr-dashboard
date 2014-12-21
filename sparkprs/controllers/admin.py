from flask import render_template, g, request, abort
from flask import Blueprint

from sparkprs.models import User


admin = Blueprint('admin', __name__)


@admin.route("/add-role", methods=['POST'])
def add_role():
    if not g.user or "admin" not in g.user.roles:
        return abort(403)
    user = User.query(User.github_login == request.form["username"]).get()
    if user is None:
        user = User(github_login=request.form["username"])
    role = request.form["role"]
    if role not in user.roles:
        user.roles.append(role)
        user.put()
    return "Updated user %s; now has roles %s" % (user.github_login, user.roles)


@admin.route('/')
def admin_panel():
    if not g.user or "admin" not in g.user.roles:
        return abort(403)
    return render_template('admin.html')