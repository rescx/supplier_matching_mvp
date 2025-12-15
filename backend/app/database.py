from sqlmodel import SQLModel, create_engine, Session
import os


DB_URL = os.getenv("DATABASE_URL", "sqlite:///./supplier.db")

# SQLite needs check_same_thread disabled for FastAPI
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    from . import models  # ensure models are imported
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    with Session(engine) as session:
        yield session
