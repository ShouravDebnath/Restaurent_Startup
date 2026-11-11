"""Developer helper: freeze NEW table DDL, never connect to or migrate a database.

The migration executes the checked-in SQL, not current ORM model generation.
"""

from pathlib import Path

from restaurant_api import edge_models  # noqa: F401
from restaurant_api.models import Base
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

root = Path(__file__).resolve().parents[1]
tables = [table for table in Base.metadata.sorted_tables if table.name.startswith('edge_')
          or table.name == 'location_notifications' or table.schema == 'edge_private']
sql = ['-- Frozen additive Phase 6 DDL. No business row updates or deletes.',
       'CREATE SCHEMA edge_private;', 'REVOKE ALL ON SCHEMA edge_private FROM PUBLIC;']
for table in tables:
    sql.append(str(CreateTable(table).compile(dialect=postgresql.dialect())) + ';')
    sql.extend(str(CreateIndex(index).compile(dialect=postgresql.dialect())) + ';'
               for index in sorted(table.indexes, key=lambda item: item.name))
target = root/'services/api/migrations/sql/0007_edge_schema.sql'
if target.exists():
    raise SystemExit('0007 is frozen. Use a new additive migration; never regenerate applied DDL.')
target.write_text('\n\n'.join(sql)+'\n', encoding='utf-8')
print(f'Frozen {len(tables)} new tables; no database connection used')
