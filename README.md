# Ollie
Ollie-API

The Ollie API is an semantic search engine indexing curated resources and content in an intuitive format for mothers, children and families.

It uses langchain under the hood to power natural language responses

## Ollie API Local Deployment Guide
This guide covers the necessary dependencies and steps to run the Ollie API application locally.

### Prerequisites

Ensure you have the following installed:

- Docker
- Git

### 1. Clone the Repository
``` bash
git clone https://github.com/oliviahealth/ollie.git
cd ollie
```

### 2. Create Environment Variables
In the root of the repository, create a file named `.env`:
``` bash
touch .env
```

Add the following contents:
``` bash
POSTGRESQL_CONNECTION_STRING='postgresql+psycopg2://ichild:ichild@db:5432/ichild'
ADMIN_POSTGRESQL_CONNECTION_STRING='postgresql+psycopg2://ichild:ichild@db:5432/ichild'
POSTGRES_DSN='postgresql://ichild:ichild@db:5432/ichild'

GOOGLE_API_KEY='' # see the sharepoint documentation
OPENAI_API_KEY='' # see the sharepoint documentation
SECRET_KEY="8E72CB3EA1DE366872FB5E238A381"
```

### 3. Build and Run Containers
From the root directory:
```
docker compose up
```
Docker will:
- Pull required images
- Start PostgreSQL
- Install dependencies
- Seed database

You should see logs indicating:
- Frontend build completion
- Backend startup
- PostgreSQL initialization
- Database seeding
