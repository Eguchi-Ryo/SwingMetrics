from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import src.models.database as database
import src.schemas.user_schema as user_schemas

router = APIRouter()

@router.get("/", response_model=list[user_schemas.User])
def read_users(db: Session = Depends(database.get_db)):
    users = db.query(user_schemas.User).all()
    return users

# Add more endpoints for create, update, delete as needed