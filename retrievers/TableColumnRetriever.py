import ast
import json
from typing import List
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from psycopg2 import connect
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from utils.openai_provider import get_embeddings_model

embeddings_provider = get_embeddings_model()
class TableColumnRetriever(BaseRetriever):
    """A retriever that retrieves top-k documents for a given table and its columns based on OpenAI embedding similarity."""

    documents: List[Document]
    embeddings: List[np.ndarray]
    k: int
    openai_embeddings: object
    """Number of top results to return."""

    def _get_relevant_documents(
        self, query: str
    ) -> List[Document]:
        """Retrieve documents based on cosine similarity between embeddings."""

        query_embedding = self.openai_embeddings.embed_query(query)
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        top_k_indices = np.argsort(similarities)[-self.k:][::-1]

        documents = []

        for i in top_k_indices:
            doc = self.documents[i]
            row = json.loads(doc.page_content)

            doc_id = row.get("id")
            name = row.get("name")
            address = row.get("address")
            city = row.get("city")
            state = row.get("state")
            zip_code = row.get("zip_code")
            latitude = row.get("latitude")
            longitude = row.get("longitude")
            description = row.get("description")
            phone = row.get("phone")
            sunday_hours = row.get("sunday_hours")
            monday_hours = row.get("monday_hours")
            tuesday_hours = row.get("tuesday_hours")
            wednesday_hours = row.get("wednesday_hours")
            thursday_hours = row.get("thursday_hours")
            friday_hours = row.get("friday_hours")
            saturday_hours = row.get("saturday_hours")
            rating = row.get("rating")
            address_link = row.get("address_link")
            website = row.get("website")

            unified_address = f"{address}, {city}, {state} {zip_code}"
            confidence = 1
            hours_of_operation = [
                {"sunday": sunday_hours},
                {"monday": monday_hours},
                {"tuesday": tuesday_hours},
                {"wednesday": wednesday_hours},
                {"thursday": thursday_hours},
                {"friday": friday_hours},
                {"saturday": saturday_hours},
            ]
            is_saved = False

            try:
                latitude = float(latitude) if latitude is not None else None
                longitude = float(longitude) if longitude is not None else None
                rating = float(rating) if rating is not None else None
            except:
                pass

            document = Document(
                page_content=json.dumps({
                    "address": unified_address,
                    "addressLink": address_link,
                    "confidence": confidence,
                    "description": description,
                    "hoursOfOperation": hours_of_operation,
                    "id": doc_id,
                    "isSaved": is_saved,
                    "latitude": latitude,
                    "longitude": longitude,
                    "name": name,
                    "phone": phone,
                    "rating": rating,
                    "website": website
                }),
                metadata={"source": "test"}
            )

            documents.append(document)

        return documents


def build_table_column_retriever(connection_uri, table_name):
    conn = connect(connection_uri)
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {table_name};")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]

    embedding_idx = columns.index("embedding")

    documents = []
    embeddings = []

    for row in rows:
        row_dict = {}

        for i, col in enumerate(columns):
            if col != "embedding":
                row_dict[col] = row[i]

        documents.append(
            Document(page_content=json.dumps(row_dict, default=str))
        )

        embeddings.append(
            np.array(ast.literal_eval(row[embedding_idx]))
        )

    cursor.close()
    conn.close()

    retriever = TableColumnRetriever(
        documents=documents,
        embeddings=embeddings,
        k=10,
        openai_embeddings=embeddings_provider
    )

    return retriever
