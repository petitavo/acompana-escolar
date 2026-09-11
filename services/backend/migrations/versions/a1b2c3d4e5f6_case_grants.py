"""case_grants

Additive only: scoped, time-boxed access grants for an escalated case (A03).
No existing table is altered.
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "88bbfdf4ceb6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "school_case_grants",
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("participant_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("environment", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "user_id", "reason"),
    )
    op.create_index(op.f("ix_school_case_grants_case_id"), "school_case_grants", ["case_id"], unique=False)
    op.create_index(op.f("ix_school_case_grants_participant_id"), "school_case_grants", ["participant_id"], unique=False)
    op.create_index(op.f("ix_school_case_grants_user_id"), "school_case_grants", ["user_id"], unique=False)
    op.create_index(op.f("ix_school_case_grants_environment"), "school_case_grants", ["environment"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_school_case_grants_environment"), table_name="school_case_grants")
    op.drop_index(op.f("ix_school_case_grants_user_id"), table_name="school_case_grants")
    op.drop_index(op.f("ix_school_case_grants_participant_id"), table_name="school_case_grants")
    op.drop_index(op.f("ix_school_case_grants_case_id"), table_name="school_case_grants")
    op.drop_table("school_case_grants")
