from fastapi import FastAPI
from routers import items

app = FastAPI()
app.include_router(items.router)

@app.get("/ping")
def ping():
    return {"message": "pong"}