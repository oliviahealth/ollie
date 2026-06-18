import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from init_database import Location
from utils.openai_provider import get_embeddings_model


DATABASE_URI = os.getenv("POSTGRESQL_CONNECTION_STRING")


def build_location_embedding_text(location):
    return (
        f"name={location.name}, description={location.description}, "
        f"resource_type={location.resource_type}, address={location.address}, "
        f"city={location.city}, county={location.county}, state={location.state}, "
        f"country={location.country}, zip_code={location.zip_code}, phone={location.phone}, "
        f"website={location.website}, sunday_hours={location.sunday_hours}, "
        f"monday_hours={location.monday_hours}, tuesday_hours={location.tuesday_hours}, "
        f"wednesday_hours={location.wednesday_hours}, thursday_hours={location.thursday_hours}, "
        f"friday_hours={location.friday_hours}, saturday_hours={location.saturday_hours}, "
        f"rating={location.rating}"
    )


def reembed_locations(database_uri):
    engine = create_engine(database_uri)
    Session = sessionmaker(bind=engine)
    session = Session()
    embeddings_model = get_embeddings_model()

    try:
        locations = session.query(Location).all()
        total = len(locations)

        for index, location in enumerate(locations, start=1):
            location.embedding = embeddings_model.embed_query(
                build_location_embedding_text(location)
            )
            print(f"Rebuilt embedding for {location.name} ({total - index} remaining)")

        session.commit()
        print(f"Done. processed={total}")
    finally:
        session.close()


if __name__ == "__main__":
    if not DATABASE_URI:
        raise RuntimeError("POSTGRESQL_CONNECTION_STRING is not set")

    reembed_locations(DATABASE_URI)
