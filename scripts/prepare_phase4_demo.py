"""Add two separate synthetic calibration labs; preserve existing rows and passwords."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from dotenv import dotenv_values
from restaurant_api.models import (
    Camera,
    DiningTable,
    Location,
    LocationGrant,
    LocationOperations,
    Membership,
)
from restaurant_edge.video_sources import synthetic_mp4
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = dotenv_values(ROOT / ".env")
    seed = json.loads((ROOT / ".secrets/phase2-demo-credentials.json").read_text())
    assert seed["namespace"] == "local-phase2"
    engine = create_engine(URL.create("postgresql+psycopg", username=values["POSTGRES_USER"],
        password=values["POSTGRES_PASSWORD"], host="127.0.0.1",
        port=int(values.get("POSTGRES_PORT") or 5432), database=values["POSTGRES_DB"]), hide_parameters=True)
    folder = ROOT / ".secrets/phase4"
    folder.mkdir(exist_ok=True)
    video = folder / "synthetic.mp4"
    if not video.exists():
        synthetic_mp4(video)
    def ident(name):
        return uuid5(NAMESPACE_URL, "restaurant-ai/local-phase4/" + name)
    result, sources = {}, []
    with Session(engine) as db, db.begin():
        for letter in ["a", "b"]:
            org = seed["organizations"][letter]["id"]
            location, camera, table = [ident(letter + "-" + kind) for kind in ["location", "camera", "table"]]
            if db.get(Location, location) is None:
                db.add(Location(id=location, organization_id=org, name=f"DEMO {letter.upper()} Calibration Lab",
                    time_zone="America/New_York" if letter=="a" else "Asia/Dhaka"))
                db.flush()
                operations = db.get(LocationOperations, location)
                operations.is_synthetic = True
            for membership in db.scalars(select(Membership).where(Membership.organization_id==org, Membership.enabled.is_(True))):
                if db.get(LocationGrant, (membership.id, location)) is None:
                    db.add(LocationGrant(membership_id=membership.id, location_id=location, organization_id=org))
            reference = "synthetic_calibration_" + letter
            if db.get(Camera, camera) is None:
                db.add(Camera(id=camera, organization_id=org, location_id=location,
                              label="DEMO synthetic video", source_reference=reference))
            if db.get(DiningTable, table) is None:
                db.add(DiningTable(id=table, organization_id=org, location_id=location,
                                  label=letter.upper()+" Lab Table", seats=4))
            result[letter] = {"organization_id":org, "location_id":str(location), "camera_id":str(camera),
                              "table_id":str(table), "source_reference":reference}
            sources.append({"reference":reference,"organization_id":org,"location_id":str(location),
                "camera_id":str(camera),"kind":"mp4","synthetic":True,"authorized":True,"file":str(video)})
    configuration = folder / "sources.json"
    if not configuration.exists():
        configuration.write_text(json.dumps({"version":1,"roots":[str(folder)],"sources":sources},indent=2),encoding="utf-8")
    (folder / "demo-layout.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print("Separate synthetic A/B calibration labs prepared; existing data/passwords and private source configuration preserved.")


if __name__ == "__main__":
    main()
