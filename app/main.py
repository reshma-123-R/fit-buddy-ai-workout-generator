"""FastAPI entry point.  Run with:  uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import config
from .database import init_db
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("fitbuddy")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if not config.get_gemini_api_key():
        logger.warning("GEMINI_API_KEY is not set - plan generation will fail until you add it to .env")
    logger.info("Gemini models: workout=%s, tips=%s", config.GEMINI_PRO_MODEL, config.GEMINI_FLASH_MODEL)
    yield


app = FastAPI(
    title="FitBuddy - AI Fitness Plan Generator",
    description="Personalised 7-day workout plans and nutrition tips powered by Google Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
app.include_router(router)


@app.get("/health", tags=["API"])
def health():
    return {"status": "ok"}
