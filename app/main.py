from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import run_migrations
from app.routes.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(products_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}