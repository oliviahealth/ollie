import os
import pandas as pd
from langchain.embeddings import OpenAIEmbeddings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Location

def load_and_store_locations(embeddings_model, csv_path, database_uri):
    """
    Load location data from a CSV, insert data into the 'location' table, 
    vectorize descriptions, and store vectors in the 'embeddings' column.

    Note: This function calls OpenAIEmbeddings() which costs money to run and can be fairly expensive so try to limit this operation.
          Ideally, the vector database should only need to be loaded initially and whenever we have new data

    """

    engine = create_engine(database_uri)
    Session = sessionmaker(bind=engine)
    session = Session()

    df = pd.read_csv(csv_path)

    for _, row in df.iterrows():
        id=row['id'],
        name=row['name']
        address=row['address']
        city=row['city']
        state=row['state']
        country=row['country']
        zip_code=row['zip_code']
        county=row['county']
        latitude=row['latitude']
        longitude=row['longitude']
        description=row['description']
        phone=row['phone']
        sunday_hours=row['sunday_hours']
        monday_hours=row['monday_hours']
        tuesday_hours=row['tuesday_hours']
        wednesday_hours=row['wednesday_hours']
        thursday_hours=row['thursday_hours']
        friday_hours=row['friday_hours']
        saturday_hours=row['saturday_hours']
        rating=row['rating']
        address_link=row['address_link']
        website=row['website']
        resource_type=row['resource_type']

        text_to_embed = f"""name={name}, description={description}, address={address}, city={city}, state={state},
        country={country}, zip_code={zip_code}, county={county}, phone={phone}, sunday_hours={sunday_hours}, monday_hours={monday_hours}, tuesday_hours={tuesday_hours},
        wednesday_hours={wednesday_hours}, thursday_hours={thursday_hours}, friday_hours={friday_hours}, saturday_hours={saturday_hours}, rating={rating}, resource_type={resource_type}"""
        
        try:
            embedding = embeddings_model.embed_query(text_to_embed)

            new_location = Location(
                id=id,
                name=name,
                address=address,
                city=city,
                state=state,
                country=country,
                zip_code=zip_code,
                county=county,
                latitude=latitude,
                longitude=longitude,
                description=description,
                phone=phone,
                sunday_hours=sunday_hours,
                monday_hours=monday_hours,
                tuesday_hours=tuesday_hours,
                wednesday_hours=wednesday_hours,
                thursday_hours=thursday_hours,
                friday_hours=friday_hours,
                saturday_hours=saturday_hours,
                rating=rating,
                address_link=address_link,
                website=website,
                resource_type=resource_type,
                embedding=embedding
            )

            session.add(new_location)

            print(f"Added new location, {name}")
        except Exception as e:
            print(f"Error inserting location {row['name']}: {e}")

        session.commit()
        session.close()

# Using OpenAI embeddings for now
openai_api_key = os.getenv("OPENAI_API_KEY")
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

csv_path = "knowledge_base/locations.csv"

database_uri = os.getenv("POSTGRESQL_CONNECTION_STRING")

load_and_store_locations(embeddings_model=embeddings_model, csv_path="knowledge_base/locations.csv", database_uri=database_uri)