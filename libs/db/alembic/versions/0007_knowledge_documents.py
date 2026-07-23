"""knowledge documents

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-22

Hand-trimmed from the autogenerate output: the raw diff also included a long
list of "removed index" operations against sensor_readings, risk_scores,
camera_events, etc. -- these are TimescaleDB-internal indexes and a handful of
partial indexes created by raw SQL in migrations 0004-0006 that the ORM layer
was never told about (documented, expected drift — see DATABASE_SCHEMA.md
§22's regime split and this repo's earlier drift-check notes). Blindly
applying that output would have DROPPED indexes hypertables still depend on.
Only the genuinely new knowledge_documents table is kept here.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("document_class", sa.String(), nullable=False),
        sa.Column("authority", sa.String(), server_default="internal", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section_reference", sa.String(), nullable=True),
        sa.Column("version", sa.String(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equipment_type_scope", sa.String(), nullable=True),
        sa.Column("hazard_class_scope", sa.String(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_knowledge_documents_created_by_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_documents")),
    )
    op.create_index("idx_knowledge_documents_class", "knowledge_documents", ["document_class"], unique=False)
    op.create_index(
        "idx_knowledge_documents_current", "knowledge_documents", ["document_class", "superseded_at"], unique=False
    )
    op.execute(
        "CREATE TRIGGER trg_knowledge_documents_updated_at BEFORE UPDATE ON knowledge_documents "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_documents_updated_at ON knowledge_documents")
    op.drop_index("idx_knowledge_documents_current", table_name="knowledge_documents")
    op.drop_index("idx_knowledge_documents_class", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
