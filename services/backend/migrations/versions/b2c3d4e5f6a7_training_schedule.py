"""training_schedule

Additive only: controlled dataset-build / retraining cadence (A05/A06).
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "school_training_schedules",
        sa.Column("institution_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("cadence_days", sa.Integer(), nullable=False),
        sa.Column("auto_retrain", sa.Boolean(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("environment", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["school_institutions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("institution_id"),
    )
    op.create_index(op.f("ix_school_training_schedules_environment"), "school_training_schedules", ["environment"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_school_training_schedules_environment"), table_name="school_training_schedules")
    op.drop_table("school_training_schedules")
