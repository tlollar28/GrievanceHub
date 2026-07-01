from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.routes.cases import router as cases_router
from app.api.routes.sources import router as sources_router
from app.config import REPORT_DIR

load_dotenv()

app = FastAPI(title="GrievanceHub")

app.include_router(sources_router)
app.include_router(cases_router)

REPORT_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "GrievanceHub",
    }
