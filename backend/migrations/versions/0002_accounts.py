"""Accounts: users, daily usage (limits and AI cost) and the owner of each exercise

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pro_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mp_preapproval_id", sa.String(64), nullable=True, unique=True),
        sa.Column("mp_status", sa.String(20), nullable=True),
    )
    op.create_table(
        "daily_usage",
        sa.Column("user_id", sa.String(64), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("exercises", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ai_cost_micro_usd", sa.Integer(), nullable=False, server_default="0"),
    )
    # Existing exercises keep user_id NULL: they were made before accounts existed
    with op.batch_alter_table("exercises") as batch:
        batch.add_column(sa.Column("user_id", sa.String(64), nullable=True))
        batch.create_foreign_key("fk_exercises_user_id", "users", ["user_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_exercises_user_created", ["user_id", "created_at"])


def downgrade():
    with op.batch_alter_table("exercises") as batch:
        batch.drop_index("ix_exercises_user_created")
        batch.drop_constraint("fk_exercises_user_id", type_="foreignkey")
        batch.drop_column("user_id")
    op.drop_table("daily_usage")
    op.drop_table("users")
