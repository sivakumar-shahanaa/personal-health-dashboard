# to read and write to the database file
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


# defines where the database file will live

# first looks for Render's PostGres string first 
# if not, it defaults to my local private SQLite file
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./analytics.db")
if DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread":False}
else:
    connect_args = {}

# building the connection engine
# the database is like a locked vault
# engine is the physical key to reach and write bytes into the file
engine = create_engine(DB_URL, connect_args = connect_args)

# create a template factory for database sessions (our temporary clipboards)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# create the core class that all database model blueprints will inherit
# when the server boots, it looks at this registry to build the table
Base = declarative_base()

# cleanup function
def get_db():
    db = SessionLocal()
    try:
        # for an API request, turns over the open database session to route logic
        yield db
    finally:
        # closes when done
        db.close()