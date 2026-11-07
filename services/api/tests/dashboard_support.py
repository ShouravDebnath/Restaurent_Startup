"""Shared synthetic dashboard test clients; credential-bearing objects hide their repr."""
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from restaurant_api.models import DiningTable


@dataclass(repr=False)
class DashboardSuite:
    suite: object
    seed: dict
    layout: dict
    clients: dict

    def table(self, table_id):
        with Session(self.suite.admin) as db:
            return db.get(DiningTable, UUID(str(table_id)))

    def perform(self, table_id, action, *, demo=False, actor="a_owner", expected=None,
                key=None, client=None, **extras):
        table = self.table(table_id)
        body = {"action": action, "request_key": str(key or uuid4()),
                "expected_revision": table.operational_revision if expected is None else expected}
        if demo:
            body["table_id"] = str(table_id)
            path = f"/v1/locations/{table.location_id}/demo/events"
        else:
            path = f"/v1/tables/{table_id}/actions"
        body.update(extras)
        return (client or self.clients[actor]).request("POST", path, json=body)

    def prepare(self, table_id, state):
        if state in {"AVAILABLE", "CLEANING", "OUT_OF_SERVICE"}:
            assert self.perform(table_id, "vacant", demo=True).status_code == 200
        if state in {"OCCUPIED", "RESET_PENDING", "CLEANING"}:
            assert self.perform(table_id, "arrive", demo=True).status_code == 200
        if state in {"RESET_PENDING", "CLEANING"}:
            assert self.perform(table_id, "depart", demo=True).status_code == 200
        if state == "CLEANING":
            assert self.perform(table_id, "start_cleaning").status_code == 200
        if state == "AVAILABLE":
            assert self.perform(table_id, "mark_ready", confirmed=True).status_code == 200
        if state == "OUT_OF_SERVICE":
            assert self.perform(table_id, "out_of_service", reason="maintenance").status_code == 200


