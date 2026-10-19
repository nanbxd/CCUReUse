"""CaspianHub market prices and event artwork / end time."""
from alembic import op
import sqlalchemy as sa

revision = 'h20261019hub'
down_revision = 'e20261019events'
branch_labels = None
depends_on = None


def upgrade():
    fields = {
        'listings': [sa.Column('price', sa.Integer(), nullable=False, server_default='0')],
        'events': [sa.Column('banner', sa.Text(), nullable=False, server_default=''),
                   sa.Column('end_date', sa.DateTime(timezone=True), nullable=True)],
    }
    for table, columns in fields.items():
        existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)


def downgrade():
    op.drop_column('events', 'end_date')
    op.drop_column('events', 'banner')
    op.drop_column('listings', 'price')
