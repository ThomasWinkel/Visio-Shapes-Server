"""add_teams_feature

Revision ID: 13dfc56ae7e5
Revises: ffcebb9c4161
Create Date: 2026-02-27 00:01:12.304810

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '13dfc56ae7e5'
down_revision = 'ffcebb9c4161'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()

    # Create team_membership only if it doesn't exist yet
    if 'team_membership' not in existing_tables:
        op.create_table('team_membership',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('team_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'team_id')
        )

    # Drop user_team_table only if it still exists
    if 'user_team_table' in existing_tables:
        op.drop_table('user_team_table')

    # Add team_id to shapes if not present
    shapes_cols = [c['name'] for c in inspector.get_columns('shapes')]
    if 'team_id' not in shapes_cols:
        with op.batch_alter_table('shapes', schema=None) as batch_op:
            batch_op.add_column(sa.Column('team_id', sa.Integer(), nullable=True))

    # Add team_id to stencils if not present
    stencils_cols = [c['name'] for c in inspector.get_columns('stencils')]
    if 'team_id' not in stencils_cols:
        with op.batch_alter_table('stencils', schema=None) as batch_op:
            batch_op.add_column(sa.Column('team_id', sa.Integer(), nullable=True))

    # Add visibility to teams if not present
    teams_cols = [c['name'] for c in inspector.get_columns('teams')]
    if 'visibility' not in teams_cols:
        with op.batch_alter_table('teams', schema=None) as batch_op:
            batch_op.add_column(sa.Column('visibility', sa.String(length=10),
                                          nullable=False, server_default='public'))
            batch_op.alter_column('description',
                   existing_type=sa.VARCHAR(),
                   nullable=True)


def downgrade():
    with op.batch_alter_table('teams', schema=None) as batch_op:
        batch_op.alter_column('description',
               existing_type=sa.VARCHAR(),
               nullable=False)
        batch_op.drop_column('visibility')

    with op.batch_alter_table('stencils', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('team_id')

    with op.batch_alter_table('shapes', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('team_id')

    op.create_table('user_team_table',
    sa.Column('user_id', sa.INTEGER(), nullable=True),
    sa.Column('team_id', sa.INTEGER(), nullable=True),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], )
    )
    op.drop_table('team_membership')
