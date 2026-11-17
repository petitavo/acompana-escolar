"""checkins

Additive only: cuestionarios breves del piloto (PHQ-2 semanal, contacto social diario,
contexto mensual).
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "school_checkins",
        sa.Column("participant_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("environment", sa.String(length=4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["participant_id"], ["participants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_school_checkins_environment"), "school_checkins", ["environment"], unique=False)
    op.create_index(op.f("ix_school_checkins_participant_id"), "school_checkins", ["participant_id"], unique=False)
    op.create_index(op.f("ix_school_checkins_code"), "school_checkins", ["code"], unique=False)
    op.create_index(op.f("ix_school_checkins_applied_at"), "school_checkins", ["applied_at"], unique=False)


def downgrade():
    for name in ("applied_at", "code", "participant_id", "environment"):
        op.drop_index(op.f("ix_school_checkins_" + name), table_name="school_checkins")
    op.drop_table("school_checkins")
