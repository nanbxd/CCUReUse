"""Add the Caspian Events module and verified organizer role.

Revision ID: e20261019events
Revises: d957603cf0a1
"""
from alembic import op
import sqlalchemy as sa

revision = 'e20261019events'
down_revision = 'd957603cf0a1'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'is_organizer' not in {c['name'] for c in sa.inspect(bind).get_columns('users')}:
        op.add_column('users', sa.Column('is_organizer', sa.Boolean(), nullable=False, server_default=sa.false()))
    # checkfirst also supports installations initialized by the existing startup migration.
    from app.event_models import Event, Ticket, Review, EventInterest, EventNotification
    for model in (Event, Ticket, Review, EventInterest, EventNotification):
        model.__table__.create(bind, checkfirst=True)


def downgrade():
    for name in ('event_notifications', 'event_interests', 'reviews', 'tickets', 'events'):
        op.drop_table(name)
    op.drop_column('users', 'is_organizer')
