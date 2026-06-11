import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from database import init_db
from routes import api, dashboard, webhook

# Initialise DB tables immediately (also fires before startup in testing)
init_db()

app = FastAPI(title="InstaBot", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(webhook.router)
app.include_router(dashboard.router)
app.include_router(api.router)


@app.on_event("startup")
async def startup():
    logging.getLogger("main").info("InstaBot started ✓")


@app.get("/health")
async def health():
    return {"status": "ok"}
