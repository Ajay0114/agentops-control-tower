
"""Create initial platform foundation.

Revision ID: 0001_platform_foundation
Revises:
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_platform_foundation"

down_revision = None

branch_labels = None

depends_on = None


def upgrade():

    op.create_table(
        "organizations",

        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "slug",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.PrimaryKeyConstraint(
            "id",
            name="pk_organizations",
        ),

        sa.UniqueConstraint(
            "slug",
            name="uq_organizations_slug",
        ),
    )

    op.create_table(
        "projects",

        sa.Column(
            "id",
            sa.Uuid(),
            nullable=False,
        ),

        sa.Column(
            "organization_id",
            sa.Uuid(),
            nullable=False,
        ),

        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "slug",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
            name="fk_projects_organization_id_organizations",
        ),

        sa.PrimaryKeyConstraint(
            "id",
            name="pk_projects",
        ),

        sa.UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_projects_organization_slug",
        ),
    )

    op.create_index(
        "ix_projects_organization_id",
        "projects",
        ["organization_id"],
    )


def downgrade():

    op.drop_index(
        "ix_projects_organization_id",
        table_name="projects",
    )

    op.drop_table("projects")

    op.drop_table("organizations")
