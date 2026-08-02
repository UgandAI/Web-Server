from fastapi import FastAPI, status
from app.db.session import check_db_connection

app = FastAPI(
    title="UgandAI API",
    description="UgandAI Backend Modular Monolith API",
    version="1.0.0",
)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    is_connected = check_db_connection()
    return {
        "status": "ok",
        "database": "connected" if is_connected else "unavailable",
    }
