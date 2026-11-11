"""Restore an archive into a NEW database on the explicitly marked test server.

Never migrates the business database, drops a database, or deletes an archive.
Private configuration and diagnostic details stay under .secrets/.
"""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from restaurant_api import edge_models  # noqa: F401
from restaurant_api.management import migrate
from restaurant_api.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    backup = args.backup.resolve(strict=True)
    if not backup.is_relative_to((ROOT/'.secrets/backups').resolve()) or backup.suffix != '.dump':
        raise RuntimeError('Select a private project backup archive')
    config = json.loads((ROOT/'.secrets/phase2-test.json').read_text(encoding='utf-8'))
    container = config['container']
    if not container.startswith('restaurant-phase2-test-'):
        raise RuntimeError('Refusing an unmarked server')
    info = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
    if (info['Config'].get('Labels', {}).get('restaurant.phase2-test') != 'true'
            or info['Mounts'] or '/var/lib/postgresql/data' not in info['HostConfig'].get('Tmpfs', {})):
        raise RuntimeError('Isolated test container safety checks failed')
    name = 'phase2_security_test_phase6_restore_' + uuid4().hex[:10]
    url = URL.create('postgresql+psycopg', username=config['username'], password=config['password'],
                     host='127.0.0.1', port=config['port'], database=config['database'])
    admin = create_engine(url, hide_parameters=True)
    with admin.connect().execution_options(isolation_level='AUTOCOMMIT') as db:
        db.exec_driver_sql('CREATE DATABASE "' + name + '"')
    with backup.open('rb') as archive:
        result = subprocess.run(['docker', 'exec', '-i', container, 'pg_restore', '--no-owner',
                                 '--no-privileges', '--username', config['username'], '--dbname', name],
                                stdin=archive, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError('Private restore failed; diagnostics withheld')
    engine = create_engine(url.set(database=name), hide_parameters=True)
    records = {}
    with engine.connect() as db:
        for schema in ('public', 'identity'):
            for table in db.scalars(text('SELECT tablename FROM pg_tables WHERE schemaname=:schema'), {'schema': schema}):
                if table == 'alembic_version':
                    continue
                records[schema+'.'+table] = db.scalars(text('SELECT to_jsonb(t) FROM '+schema+'.'+table+' t')).all()
    private = ROOT/'.secrets/phase6-implementation'
    private.mkdir(exist_ok=True)
    # Retain a private baseline for row-by-row preservation checks after an approved migration.
    with (private/('restored-records-'+name+'.json')).open('x', encoding='utf-8') as handle:
        json.dump(records, handle)
    migrate(engine)
    migrate(engine)
    with engine.connect() as db:
        for table, rows in records.items():
            actual = db.scalars(text('SELECT to_jsonb(t) FROM '+table+' t')).all()
            if not all(any(all(current.get(key)==value for key,value in row.items())
                           for current in actual) for row in rows):
                raise RuntimeError('Restored record preservation failed')
        differences = compare_metadata(MigrationContext.configure(db, opts={'include_schemas': True}), Base.metadata)
        if differences:
            (private/'migration-model-diff.txt').write_text(str(differences), encoding='utf-8')
            raise RuntimeError('Migration/model mismatch; private details saved')
        if db.scalar(text('SELECT version_num FROM alembic_version')) != '0008':
            raise RuntimeError('Unexpected migration head')
    report = {'verified_at_utc': datetime.now(UTC).isoformat(), 'isolated_database': name,
                  'backup': str(backup.relative_to(ROOT)), 'backup_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
                  'migration_head': '0008', 'preserved_records': sum(map(len, records.values())),
                  'model_differences': 0, 'business_database_untouched': True}
    (private/'migration-rehearsal.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    engine.dispose()
    admin.dispose()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:  # noqa: BLE001 -- never print private DB/restore diagnostics
        print('Migration rehearsal stopped:', type(error).__name__, '; private database details withheld.')
        raise SystemExit(1) from None
