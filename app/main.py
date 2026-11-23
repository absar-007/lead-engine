
import os
import secrets

from dotenv import load_dotenv
from fastapi import Header, HTTPException
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel, Field

from app.db import init_db
from app.airtable_sync import sync_all_pending, sync_lead
from app.service import process_lead
from pathlib import Path

from fastapi.responses import FileResponse

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # creates the database table on startup if it doesn't exist
    yield


app = FastAPI(title='Lead Engine', lifespan=lifespan)
load_dotenv()
ADMIN_KEY = os.getenv('ADMIN_KEY')
STATIC = Path(__file__).parent / 'static'

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
@app.post('/admin/sync-pending')
def sync_pending(x_admin_key: str | None = Header(default=None)):
    if not ADMIN_KEY or not x_admin_key or not secrets.compare_digest(x_admin_key, ADMIN_KEY):
        raise HTTPException(status_code=403, detail='Forbidden')
    return sync_all_pending()
@app.get('/', include_in_schema=False)
def home():
    return FileResponse(STATIC / 'index.html')