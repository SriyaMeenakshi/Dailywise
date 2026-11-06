"""daily reviews

Revision ID: 0004
Revises: 0003
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("review_date", sa.Date(), nullable=False),
        sa.Column("accomplished", sa.Text()),
        sa.Column("remaining", sa.Text()),
        sa.Column("blockers", sa.Text()),
        sa.Column("tomorrow_focus", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "review_date", name="uq_daily_reviews_user_date"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE daily_reviews ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY daily_reviews_owner ON daily_reviews FOR ALL TO authenticated "
            "USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())"
        )


def downgrade() -> None:
    op.drop_table("daily_reviews")
