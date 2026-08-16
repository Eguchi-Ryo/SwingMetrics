from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import src.models.database as database
import src.schemas.user_schema as user_schemas
import src.schemas.swing_schema as swing_schemas
import src.schemas.benchmark_model_schema as benchmark_model_schemas
from .api.router import router

# Database setup
engine = database.get_engine()
database.Base.metadata.create_all(bind=engine)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="SwingMetrics AI API")

@app.on_event("startup")
async def startup():
    # Database setup on startup
    pass

# Include API routers
app.include_router(router, prefix="/api/v1", tags=["API"])

# Frontend routing
from fastapi.responses import HTMLResponse
import os

@app.get("/", response_class=HTMLResponse)
def read_root():
    with open("templates/index.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=status.HTTP_200_OK)

@app.get("/upload", response_class=HTMLResponse)
def upload_video_page():
    with open("templates/upload.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=status.HTTP_200_OK)

@app.get("/analysis/{id}", response_class=HTMLResponse)
def analysis_page(id: int):
    with open("templates/analysis.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=status.HTTP_200_OK)

@app.get("/models", response_class=HTMLResponse)
def models_page():
    with open("templates/models.html", "r") as f:
        return HTMLResponse(content=f.read(), status_code=status.HTTP_200_OK)
