"""projects, phases, subtasks, dependencies, task history, priority columns

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNED_TABLES = ("projects", "project_phases", "subtasks", "task_dependencies", "task_logs", "user_preferences")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _user_fk() -> sa.Column:
    return sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("objective", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.CheckConstraint("status IN ('active', 'on_hold', 'completed', 'archived')", name="ck_projects_status"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])

    op.create_table(
        "project_phases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
    )
    op.create_index("ix_project_phases_project_id", "project_phases", ["project_id"])

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("priority_weights", sa.JSON()),
        *_timestamps(),
    )

    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("project_id", sa.Uuid()))
        batch.add_column(sa.Column("phase_id", sa.Uuid()))
        batch.add_column(sa.Column("impact", sa.Integer(), nullable=False, server_default="3"))
        batch.add_column(sa.Column("priority_score", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("priority_computed", sa.Float(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("priority_override", sa.Integer()))
        batch.add_column(sa.Column("priority_factors", sa.JSON()))
        batch.add_column(sa.Column("priority_computed_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key("fk_tasks_project_id", "projects", ["project_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_tasks_phase_id", "project_phases", ["phase_id"], ["id"], ondelete="SET NULL")
        batch.create_check_constraint("ck_tasks_impact", "impact BETWEEN 1 AND 5")
        batch.create_check_constraint(
            "ck_tasks_priority_override", "priority_override IS NULL OR priority_override BETWEEN 0 AND 100"
        )
        batch.create_index("ix_tasks_project_id", ["project_id"])
        batch.create_index("ix_tasks_phase_id", ["phase_id"])

    op.create_table(
        "subtasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("estimated_minutes", sa.Integer()),
        sa.Column("done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.CheckConstraint("estimated_minutes IS NULL OR estimated_minutes > 0", name="ck_subtasks_estimate"),
    )
    op.create_index("ix_subtasks_task_id", "subtasks", ["task_id"])

    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("depends_on_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        _user_fk(),
        sa.CheckConstraint("task_id <> depends_on_id", name="ck_task_dependencies_not_self"),
    )
    op.create_index("ix_task_dependencies_depends_on", "task_dependencies", ["depends_on_id"])
    op.create_index("ix_task_dependencies_user_id", "task_dependencies", ["user_id"])

    op.create_table(
        "task_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        _user_fk(),
        sa.Column("task_id", sa.Uuid(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("detail", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_task_logs_task_created", "task_logs", ["task_id", "created_at"])

    if op.get_bind().dialect.name == "postgresql":
        for table in OWNED_TABLES:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(
                f"CREATE POLICY {table}_owner ON {table} FOR ALL TO authenticated "
                f"USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())"
            )


def downgrade() -> None:
    op.drop_table("task_logs")
    op.drop_table("task_dependencies")
    op.drop_table("subtasks")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_phase_id")
        batch.drop_index("ix_tasks_project_id")
        batch.drop_constraint("ck_tasks_priority_override", type_="check")
        batch.drop_constraint("ck_tasks_impact", type_="check")
        batch.drop_constraint("fk_tasks_phase_id", type_="foreignkey")
        batch.drop_constraint("fk_tasks_project_id", type_="foreignkey")
        for column in (
            "priority_computed_at", "priority_factors", "priority_override", "priority_computed",
            "priority_score", "impact", "phase_id", "project_id",
        ):
            batch.drop_column(column)
    op.drop_table("user_preferences")
    op.drop_table("project_phases")
    op.drop_table("projects")
