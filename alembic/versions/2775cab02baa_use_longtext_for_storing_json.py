"""Use LONGTEXT for storing JSON

Revision ID: 2775cab02baa
Revises: 56b17e242cb9
Create Date: 2015-01-01 16:38:29.463973

"""

# revision identifiers, used by Alembic.
revision = '2775cab02baa'
down_revision = '56b17e242cb9'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.alter_column('jira_issue', 'issue_json',
                   type_=mysql.LONGTEXT())
    op.alter_column('pull_request', 'pr_json',
                   type_=mysql.LONGTEXT())
    op.alter_column('pull_request', 'files_json',
                   type_=mysql.LONGTEXT())
    op.alter_column('user', 'github_json',
                   type_=mysql.LONGTEXT())

def downgrade():
    op.alter_column('jira_issue', 'issue_json',
                   type_=mysql.TEXT())
    op.alter_column('pull_request', 'pr_json',
                   type_=mysql.TEXT())
    op.alter_column('pull_request', 'files_json',
                   type_=mysql.TEXT())
    op.alter_column('user', 'github_json',
                   type_=mysql.TEXT())
