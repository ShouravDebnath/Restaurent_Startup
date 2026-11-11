"""Actual PostgreSQL container restart on a NEW labeled persistent test volume.

Never targets the business or earlier test containers. The new volume/container
are retained. This is database crash/restart evidence, not camera/AI evaluation.
"""

import json
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from restaurant_api.management import migrate, provision_runtime, seed_demo

ROOT = Path(__file__).resolve().parents[3]


def docker(*args, **kwargs):
    result = subprocess.run(['docker', *args], capture_output=True, check=False, **kwargs)
    assert result.returncode == 0, 'Isolated recovery-container operation failed; private details withheld'
    return result.stdout.decode().strip()


def test_postgres_restart_preserves_committed_receipts_and_unique_task(tmp_path):
    name = 'restaurant-phase6-recovery-'+uuid4().hex[:10]
    volume = name+'-data'
    database = 'phase2_security_test_phase6_recovery'
    username, password = 'phase6_test', secrets.token_urlsafe(36)
    with socket.socket() as probe:
        probe.bind(('127.0.0.1',0))
        requested_port = probe.getsockname()[1]
    env = dict(os.environ, POSTGRES_USER=username, POSTGRES_PASSWORD=password, POSTGRES_DB=database)
    docker('volume','create','--label','restaurant.phase6-test=true',volume)
    container = docker('run','--detach','--name',name,'--label','restaurant.phase6-test=true',
        '--env','POSTGRES_USER','--env','POSTGRES_PASSWORD','--env','POSTGRES_DB',
        '--publish',f'127.0.0.1:{requested_port}:5432','--mount',f'type=volume,source={volume},target=/var/lib/postgresql/data',
        'postgres:16-alpine', env=env)
    info = json.loads(docker('inspect',container))[0]
    assert info['Config']['Labels']['restaurant.phase6-test']=='true'
    assert info['Name']=='/'+name
    assert all(mount['Name']==volume for mount in info['Mounts'])
    port = int(info['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort'])
    assert port == requested_port
    url = URL.create('postgresql+psycopg',username=username,password=password,host='127.0.0.1',port=port,database=database)
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True, connect_args={'connect_timeout':2})

    def ready():
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            status = subprocess.run(['docker','exec',container,'pg_isready','-U',username,'-d',database],
                                    capture_output=True,check=False)
            if status.returncode == 0:
                try:
                    # pg_isready inside the container can see its temporary init
                    # socket server before the published TCP listener is ready.
                    with engine.connect() as db:
                        if db.scalar(text('SELECT current_database()')) == database:
                            return
                except SQLAlchemyError:
                    pass
            time.sleep(.2)
        raise AssertionError('New isolated recovery database did not become ready')

    try:
        ready()
        migrate(engine)
        runtime_user = 'restaurant_recovery_'+uuid4().hex[:8]
        runtime_password = secrets.token_urlsafe(36)
        provision_runtime(engine,runtime_user,runtime_password)
        seed = seed_demo(engine,tmp_path/'private-accounts.json','recovery-'+uuid4().hex[:8])
        loc = seed['organizations']['a']['locations'][0]
        org = seed['organizations']['a']['id']
        resources = seed['organizations']['a']['resources_1']
        with engine.begin() as db:
            db.execute(text('UPDATE location_operations SET is_synthetic=true WHERE location_id=:id'),{'id':loc})
        # Reuse the actual application API helper with a fresh private test suite.
        # This part is an ASGI signature test; verified TLS is tested separately.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from fastapi.testclient import TestClient

        from restaurant_api.database import get_engine
        from restaurant_api.main import create_app
        from restaurant_api.settings import get_settings

        from .conftest import Suite
        from .test_edge_transport import batch, configure, observation
        old_url, old_enabled = os.environ.get('DATABASE_URL'), os.environ.get('EDGE_SYNC_ENABLED')
        os.environ['DATABASE_URL'] = url.set(username=runtime_user,password=runtime_password).render_as_string(hide_password=False)
        os.environ['EDGE_SYNC_ENABLED'] = 'true'
        get_settings.cache_clear()
        get_engine.cache_clear()
        runtime = get_engine()
        suite = Suite(engine,runtime,create_app(),seed,'recovery')
        clients = {key:suite.login(value) for key,value in seed['accounts'].items()}
        client = TestClient(suite.app,base_url='https://testserver',client=('recovery-'+uuid4().hex,51000))
        edge = SimpleNamespace(suite=suite,clients=clients,client=client,org=org,loc=loc,camera=resources['camera_id'],
            table=resources['table_id'],key=Ed25519PrivateKey.generate(),kid=uuid4(),request_id=uuid4(),stream=uuid4())
        try:
            configure(edge,'SYNTHETIC_WORKFLOW_TEST')
            episode = uuid4()
            one = observation(edge,1).model_copy(update={'kind':'fixture_arrive','reason':'FIXTURE',
                'state':'OCCUPIED','occupancy_session_id':episode})
            two = observation(edge,2).model_copy(update={'kind':'fixture_depart','reason':'FIXTURE',
                'state':'RESET_PENDING','occupancy_session_id':episode})
            assert batch(edge,one,two).status_code == 200
            docker('restart',container)
            ready()
            # Recreate API and dispose its pool, retaining the same persistent DB.
            runtime.dispose()
            get_engine.cache_clear()
            client.close()
            edge.client = TestClient(create_app(),base_url='https://testserver')
            assert batch(edge,one,two).status_code == 200
            with engine.connect() as db:
                assert db.scalar(text('SELECT count(*) FROM edge_receipts WHERE device_id=:id'),{'id':edge.device}) == 2
                assert db.scalar(text('SELECT count(*) FROM staff_tasks WHERE table_id=:id'),{'id':edge.table}) == 1
                assert db.scalar(text("SELECT current_state FROM dining_tables WHERE id=:id"),{'id':edge.table}) == 'RESET_PENDING'
            report = {'container':name,'volume':volume,'actual_postgres_restart':True,'api_recreated':True,
                      'receipts':2,'reset_tasks':1,'business_database_untouched':True,'volume_retained':True}
            (ROOT/'.secrets/phase6-implementation/database-restart.json').write_text(json.dumps(report,indent=2))
        finally:
            edge.client.close()
            for actor in clients.values():
                actor.client.close()
            runtime.dispose()
            get_engine.cache_clear()
            for key,value in [('DATABASE_URL',old_url),('EDGE_SYNC_ENABLED',old_enabled)]:
                if value is None:
                    os.environ.pop(key,None)
                else:
                    os.environ[key]=value
            get_settings.cache_clear()
    finally:
        engine.dispose()
        docker('stop',container)  # New test server only; volume and files are retained.
