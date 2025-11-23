# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from contextlib import asynccontextmanager

from app.route import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    # Base.metadata.create_all(bind=engine)
    print("Database connection open!")
    yield
    # shutdown
    engine.dispose()
    print("Database connection close!")

app = FastAPI(lifespan=lifespan)

origins = [
    "http://localhost:3000",
    "https://chotu-dairy.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Welcome to Chotu Dairy!"}


app.include_router(api_router, prefix="/chotu-dairy")
