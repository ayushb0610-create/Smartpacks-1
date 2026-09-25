"""
Create tables (if needed) and seed reference data (commodities, materials,
cities) from app/seed_data.py.

Idempotent: safe to run repeatedly. Existing rows are matched by their
natural key (commodity/material name, or state+city) and updated in place
rather than duplicated, so re-running this after editing seed_data.py
pushes the edit through instead of piling up duplicates.

Usage:
    python -m scripts.seed_db
"""
from __future__ import annotations

import logging

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import City, Commodity, Material
from app.seed_data import CITIES, COMMODITIES, MATERIALS

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("seed_db")


def upsert(session, model, natural_key: dict, values: dict):
    stmt = select(model).filter_by(**natural_key)
    row = session.execute(stmt).scalar_one_or_none()
    if row is None:
        row = model(**{**natural_key, **values})
        session.add(row)
        return "inserted"
    for k, v in values.items():
        setattr(row, k, v)
    return "updated"


def main() -> None:
    log.info("Creating tables if they don't exist (target: %s)", engine.url)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    counts = {"inserted": 0, "updated": 0}
    try:
        for c in COMMODITIES:
            data = dict(c)
            name = data.pop("name")
            r = upsert(session, Commodity, {"name": name}, data)
            counts[r] += 1

        for m in MATERIALS:
            data = dict(m)
            name = data.pop("name")
            r = upsert(session, Material, {"name": name}, data)
            counts[r] += 1

        for city in CITIES:
            data = dict(city)
            state, town = data.pop("state"), data.pop("city")
            r = upsert(session, City, {"state": state, "city": town}, data)
            counts[r] += 1

        session.commit()
        log.info(
            "Seed complete: %d inserted, %d updated (commodities=%d materials=%d cities=%d).",
            counts["inserted"], counts["updated"],
            len(COMMODITIES), len(MATERIALS), len(CITIES),
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
