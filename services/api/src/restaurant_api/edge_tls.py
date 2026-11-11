"""Local-only TLS listener for the existing application. No global CA installation."""

import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cert', type=Path, required=True)
    parser.add_argument('--key', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8443)
    parser.add_argument('--env-file', type=Path, help='Private local .env; use its restricted application login only')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535 or not args.cert.is_file() or not args.key.is_file():
        parser.exit(1, 'Select a valid private certificate/key and local unprivileged port.\n')
    if args.env_file:
        from dotenv import dotenv_values
        from sqlalchemy.engine import URL
        values = dotenv_values(args.env_file)
        if not all(values.get(name) for name in ('APP_DB_USER','APP_DB_PASSWORD','POSTGRES_DB')):
            parser.exit(1, 'Private restricted database configuration is incomplete.\n')
        os.environ['DATABASE_URL'] = URL.create('postgresql+psycopg',username=values['APP_DB_USER'],
            password=values['APP_DB_PASSWORD'],host='127.0.0.1',port=int(values.get('POSTGRES_PORT') or 5432),
            database=values['POSTGRES_DB']).render_as_string(hide_password=False)
        os.environ['APP_ENV'] = values.get('APP_ENV') or 'development'
        os.environ['EDGE_SYNC_ENABLED'] = 'true'
        os.environ['DEMO_MODE'] = values.get('DEMO_MODE') or 'true'
        from restaurant_api.settings import get_settings
        get_settings.cache_clear()
    import uvicorn
    uvicorn.run('restaurant_api.main:app', host='127.0.0.1', port=args.port, ssl_certfile=str(args.cert),
                ssl_keyfile=str(args.key), proxy_headers=False, access_log=False, log_level='warning',
                timeout_keep_alive=2, timeout_graceful_shutdown=5)


if __name__ == '__main__':
    main()
