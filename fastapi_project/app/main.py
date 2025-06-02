from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app import models, schemas, crud
from app.database import SessionLocal, engine, Base

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/items/", response_model=schemas.ItemRead)
def create_item(item: schemas.ItemCreate, db: Session = Depends(get_db)):
    return crud.create_item(db=db, item=item)

@app.get("/items/", response_model=list[schemas.ItemRead])
def read_items(db: Session = Depends(get_db)):
    return crud.get_items(db=db)
