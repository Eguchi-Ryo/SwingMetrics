from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import src.models.database as database
import src.schemas.benchmark_model_schema as benchmark_model_schemas

router = APIRouter()

@router.get("/", response_model=list[benchmark_model_schemas.BenchmarkModel])
def read_benchmark_models(db: Session = Depends(database.get_db)):
    models = db.query(benchmark_model_schemas.BenchmarkModel).all()
    return models

# Add more endpoints for create, update, delete as needed