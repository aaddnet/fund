from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://fund:fund@db:5432/fund"
)
