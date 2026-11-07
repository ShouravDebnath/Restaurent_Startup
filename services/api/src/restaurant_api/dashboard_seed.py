"""Explicit, repeatable synthetic dashboard setup. Never reset an existing table/user."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from restaurant_api.database import set_identity
from restaurant_api.models import (
    DiningTable,
    Location,
    LocationGrant,
    LocationOperations,
    Membership,
)


def seed_dashboard(engine, seed: dict) -> dict:
    namespace = seed["namespace"]
    result = {"namespace": namespace, "locations": {}}
    states = {
        "a": ["AVAILABLE", "OCCUPIED", "RESET_PENDING", "CLEANING", "UNKNOWN", "OUT_OF_SERVICE"],
        "b": ["RESET_PENDING", "AVAILABLE", "UNKNOWN", "OCCUPIED", "OUT_OF_SERVICE", "CLEANING"],
    }

    def identifier(name):
        return uuid5(NAMESPACE_URL, f"restaurant-ai/{namespace}/phase3/{name}")

    with Session(engine) as db, db.begin():
        for letter in ("a", "b"):
            org = UUID(seed["organizations"][letter]["id"])
            loc_id = identifier(letter + "-dashboard")
            location = db.get(Location, loc_id)
            if location is None:
                db.add(Location(id=loc_id, organization_id=org,
                                name=f"DEMO {letter.upper()} Dining Room",
                                time_zone="America/New_York" if letter == "a" else "Asia/Dhaka"))
                db.flush()
                db.get(LocationOperations, loc_id).is_synthetic = True
            elif location.organization_id != org:
                raise ValueError("Demo location ownership mismatch; no rows reset")
            elif not db.get(LocationOperations, loc_id).is_synthetic:
                raise ValueError("Refusing to mark an existing ordinary location synthetic")
            for member in db.scalars(select(Membership).where(
                Membership.organization_id == org, Membership.enabled.is_(True)
            )):
                key = {"membership_id": member.id, "location_id": loc_id}
                if db.get(LocationGrant, key) is None:
                    db.add(LocationGrant(**key, organization_id=org))
            db.flush()
            set_identity(db, seed["accounts"][letter + "_owner"]["user_id"])
            ids = []
            for index, desired in enumerate(states[letter], start=1):
                table_id = identifier(f"{letter}-table-{index}")
                ids.append(str(table_id))
                if db.get(DiningTable, table_id) is not None:
                    continue  # Preserve all staff changes and timers on repeat setup.
                db.add(DiningTable(id=table_id, organization_id=org, location_id=loc_id,
                                   label=f"{letter.upper()}{index:02d}", seats=2 if index % 2 else 4))
                db.flush()
                operations = [("vacant", True)]
                if desired == "AVAILABLE":
                    operations += [("mark_ready", False)]
                elif desired in {"OCCUPIED", "RESET_PENDING", "CLEANING"}:
                    operations += [("arrive", True)]
                    if desired != "OCCUPIED":
                        operations += [("depart", True)]
                    if desired == "CLEANING":
                        operations += [("start_cleaning", False)]
                elif desired == "OUT_OF_SERVICE":
                    operations += [("out_of_service", False)]
                else:
                    operations += [("source_offline", True)]
                for step, (action, demo) in enumerate(operations):
                    revision = db.scalar(select(DiningTable.operational_revision).where(
                        DiningTable.id == table_id))
                    db.execute(text("""SELECT security.table_action(:t,:a,:v,:k,:f,NULL,true,:r,:d,true)"""),
                               {"t": table_id, "a": action, "v": revision,
                                "k": identifier(f"{table_id}-{step}"), "f": "0" * 64,
                                "r": "maintenance" if action == "out_of_service" else "", "d": demo})
            result["locations"][letter] = {"id": str(loc_id), "table_ids": ids}
    return result
