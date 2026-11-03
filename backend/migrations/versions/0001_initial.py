"""Initial schema: the exercises table as it existed before migrations (created by create_all)

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("original_image_path", sa.String(), nullable=True),
        sa.Column("extracted_latex", sa.Text(), nullable=False),
        sa.Column("domain_classification", sa.String(), nullable=True),
        sa.Column("symbolic_representation", sa.Text(), nullable=True),
        sa.Column("solution_steps_json", sa.Text(), nullable=True),
        sa.Column("final_result_latex", sa.Text(), nullable=True),
        sa.Column("graph_data_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_exercises_id", "exercises", ["id"])
    op.create_index("ix_exercises_created_at", "exercises", ["created_at"])


def downgrade():
    op.drop_table("exercises")
