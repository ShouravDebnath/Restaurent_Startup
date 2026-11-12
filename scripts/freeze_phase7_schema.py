"""Freeze new Phase 7 DDL without connecting to a database. Never regenerate applied SQL."""

from pathlib import Path

from restaurant_api import edge_models, workflow_models  # noqa: F401
from restaurant_api.models import Base
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

root = Path(__file__).resolve().parents[1]
target = root / "services/api/migrations/sql/0009_workflow_schema.sql"
if target.exists():
    raise SystemExit(
        "Schema already frozen; review before changing an unapproved migration."
    )
tables = [t for t in Base.metadata.sorted_tables if t.name.startswith("workflow_")]
statements = [
    "-- Additive Phase 7 tables; existing rows are not rewritten or deleted.",
    "ALTER TABLE public.edge_receipts ADD CONSTRAINT receipt_scope UNIQUE(event_id,organization_id,location_id);",
    "ALTER TABLE public.staff_tasks ADD CONSTRAINT task_scope UNIQUE(id,organization_id,location_id);",
    "ALTER TABLE public.table_events ADD CONSTRAINT event_scope UNIQUE(id,organization_id,location_id);",
]
for table in tables:
    statements.append(
        str(CreateTable(table).compile(dialect=postgresql.dialect())).rstrip() + ";"
    )
    statements.extend(
        str(CreateIndex(i).compile(dialect=postgresql.dialect())).rstrip() + ";"
        for i in sorted(table.indexes, key=lambda x: x.name)
    )
target.write_text(
    "\n\n".join("\n".join(line.rstrip() for line in s.splitlines()) for s in statements)
    + "\n",
    encoding="utf-8",
)
print(f"Frozen {len(tables)} new tables; no database access.")
