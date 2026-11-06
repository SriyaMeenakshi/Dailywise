"""AI cache and usage logs, schedule blocks, planner preferences, phase milestones

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _user_fk() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "ai_usage_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("feature", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(40)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_usage_user_created", "ai_usage_logs", ["user_id", "created_at"])

    op.create_table(
        "ai_cache",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("feature", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "cache_key", name="uq_ai_cache_user_key"),
    )

    op.create_table(
        "schedule_blocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE")),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("title", sa.String(300)),
        sa.Column("start_min", sa.Integer(), nullable=False),
        sa.Column("end_min", sa.Integer(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warning", sa.String(300)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('task', 'break', 'fixed', 'postponed')", name="ck_schedule_blocks_kind"),
        sa.CheckConstraint("start_min >= 0 AND end_min <= 1440 AND start_min < end_min", name="ck_schedule_blocks_range"),
    )
    op.create_index("ix_schedule_blocks_user_date", "schedule_blocks", ["user_id", "plan_date"])
    op.create_index("ix_schedule_blocks_task_id", "schedule_blocks", ["task_id"])

    with op.batch_alter_table("user_preferences") as batch:
        batch.add_column(sa.Column("workday_start_min", sa.Integer()))
        batch.add_column(sa.Column("workday_end_min", sa.Integer()))
        batch.add_column(sa.Column("break_minutes", sa.Integer()))
    with op.batch_alter_table("project_phases") as batch:
        batch.add_column(sa.Column("milestone", sa.String(300)))

    if op.get_bind().dialect.name == "postgresql":
        for table in ("ai_usage_logs", "ai_cache", "schedule_blocks"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY {table}_owner ON {table} FOR ALL TO authenticated "
                f"USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())"
            )


def downgrade() -> None:
    with op.batch_alter_table("project_phases") as batch:
        batch.drop_column("milestone")
    with op.batch_alter_table("user_preferences") as batch:
        for column in ("break_minutes", "workday_end_min", "workday_start_min"):
            batch.drop_column(column)
    op.drop_table("schedule_blocks")
    op.drop_table("ai_cache")
    op.drop_table("ai_usage_logs")
