from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.db import init_db
from app.service import process_lead


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates the database table on startup if it doesn't exist
    yield


app = FastAPI(title='Lead Engine', lifespan=lifespan)


class LeadInput(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    source: str | None = Field(default=None, max_length=50)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.post('/leads')
def create_lead(lead: LeadInput):
    return process_lead(lead.message, lead.source)