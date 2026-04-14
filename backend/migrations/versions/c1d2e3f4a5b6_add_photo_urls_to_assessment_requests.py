"""add photo_urls to assessment_requests

Revision ID: c1d2e3f4a5b6
Revises: a6510fbff360
Create Date: 2026-04-13 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'a6510fbff360'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('assessment_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_urls', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('assessment_requests', schema=None) as batch_op:
        batch_op.drop_column('photo_urls')
