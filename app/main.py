from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import run_migrations
from app.routes.label_templates import router as label_templates_router
from app.routes.labels import router as labels_router
from app.routes.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(products_router)
app.include_router(label_templates_router)
app.include_router(labels_router)


@app.get("/")
async def root():
    return {"message": "Hello World"}