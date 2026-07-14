from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base
from .routers import players, games, stats, reports

Base.metadata.create_all(bind=engine)

app = FastAPI(title="ECAC Hockey Stats API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(games.router)
app.include_router(stats.router)
app.include_router(reports.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
