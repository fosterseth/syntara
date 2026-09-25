"""merge forms and invocation migrations

Revision ID: 0dc201b31d3e
Revises: 2a78b3c49c72, d5b8c2f04e71
Create Date: 2026-09-25 13:37:30.571264

Merges the two heads created when devel was merged into the forms branch:
``2a78b3c49c72`` (form prompts tables) and ``d5b8c2f04e71`` (agent_execution_id
on invocations). The branches touch disjoint tables, so there is no schema
change to make here.

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0dc201b31d3e"
down_revision: str | Sequence[str] | None = ("2a78b3c49c72", "d5b8c2f04e71")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
