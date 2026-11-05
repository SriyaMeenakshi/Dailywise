"""create users categories tasks

Revision ID: 0001
Revises: 
Create Date: 2026-11-04 23:10:59.934137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OWNED_TABLES = {"users": "id", "categories": "user_id", "tasks": "user_id"}


def _enable_row_level_security() -> None:
    """Defense in depth on Supabase: the API connects as a privileged role, but if the Data API
    (PostgREST) is ever reachable, rows are still limited to their owner. Postgres only."""
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, owner_column in OWNED_TABLES.items():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_owner ON {table} FOR ALL TO authenticated "
            f"USING ({owner_column} = auth.uid()) WITH CHECK ({owner_column} = auth.uid())"
        )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('display_name', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('categories',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'name', name='uq_categories_user_name')
    )
    op.create_index(op.f('ix_categories_user_id'), 'categories', ['user_id'], unique=False)
    op.create_table('tasks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('expected_outcome', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('importance', sa.Integer(), nullable=False),
    sa.Column('urgency', sa.Integer(), nullable=False),
    sa.Column('energy', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('recurrence', sa.String(length=10), nullable=False),
    sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
    sa.Column('estimated_minutes', sa.Integer(), nullable=True),
    sa.Column('actual_minutes', sa.Integer(), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("energy IN ('low', 'medium', 'high')", name='ck_tasks_energy'),
    sa.CheckConstraint("recurrence IN ('none', 'daily', 'weekly', 'weekdays', 'monthly')", name='ck_tasks_recurrence'),
    sa.CheckConstraint("status IN ('inbox', 'not_started', 'in_progress', 'completed', 'blocked', 'archived')", name='ck_tasks_status'),
    sa.CheckConstraint('actual_minutes IS NULL OR actual_minutes >= 0', name='ck_tasks_actual'),
    sa.CheckConstraint('estimated_minutes IS NULL OR estimated_minutes > 0', name='ck_tasks_estimate'),
    sa.CheckConstraint('importance BETWEEN 1 AND 5', name='ck_tasks_importance'),
    sa.CheckConstraint('urgency BETWEEN 1 AND 5', name='ck_tasks_urgency'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_category_id'), 'tasks', ['category_id'], unique=False)
    op.create_index('ix_tasks_user_deadline', 'tasks', ['user_id', 'deadline'], unique=False)
    op.create_index('ix_tasks_user_status', 'tasks', ['user_id', 'status'], unique=False)

    _enable_row_level_security()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_tasks_user_status', table_name='tasks')
    op.drop_index('ix_tasks_user_deadline', table_name='tasks')
    op.drop_index(op.f('ix_tasks_category_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_categories_user_id'), table_name='categories')
    op.drop_table('categories')
    op.drop_table('users')

