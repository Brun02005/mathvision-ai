from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="MathVision AI",
    description="Advanced university-level mathematical and physics problem-solving platform API",
    version="1.0.0"
)

# CORS configuration — allow all localhost ports (dev)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api import router as api_router
from database import engine
import models

# Create database tables
models.Base.metadata.create_all(bind=engine)

app.include_router(api_router.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "Welcome to MathVision AI API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
