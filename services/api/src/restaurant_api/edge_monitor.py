"""Bounded server-clock health publication, independent of browser/device presence."""

import asyncio
from contextlib import contextmanager, suppress

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from restaurant_api.database import get_db


def mark_offline():
    with contextmanager(get_db)() as db:
        return db.scalar(text('SELECT security.edge_mark_offline()'))


async def monitor():
    while True:
        with suppress(SQLAlchemyError):
            await asyncio.to_thread(mark_offline)
        await asyncio.sleep(2)
