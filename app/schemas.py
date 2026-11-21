from enum import Enum
from pydantic import BaseModel, Field

class Category(str, Enum):
    sales_inquiry = 'sales_inquiry'
    support = 'support'
    partnership = 'partnership'
    spam = 'spam'
    other = 'other'

class LeadResult(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    category: Category
    priority: int = Field(ge=1, le=5)
    summary: str = Field(max_length=300)
    suggested_reply: str | None = None
    needs_human: bool = False
    injection_suspected: bool = False