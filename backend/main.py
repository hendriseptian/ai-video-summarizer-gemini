from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="AI Video Summarizer API",
    description="Backend API for AI Video Summarizer",
    version="1.0.0"
)


# Allow requests from the GitHub Pages frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "AI Video Summarizer API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
