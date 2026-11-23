from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

from app.db import init_db
from app.airtable_sync import sync_all_pending, sync_lead
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
def create_lead(lead: LeadInput, background_tasks: BackgroundTasks):
    result = process_lead(lead.message, lead.source)
    if result['saved'] and not result['duplicate']:
        background_tasks.add_task(sync_lead, result['id'])
    return result
@app.post('/admin/sync-pending')
def sync_pending():
    return sync_all_pending()