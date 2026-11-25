import os
import socket

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///leads.db')
if DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
connect_args = {}
if DATABASE_URL.startswith('postgresql'):
    connect_args['connect_timeout'] = 10
    if os.getenv('FORCE_IPV4') == '1':
        parsed = make_url(DATABASE_URL)
        connect_args['hostaddr'] = socket.getaddrinfo(
            parsed.host, parsed.port or 5432, socket.AF_INET
        )[0][4][0]
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class LeadRecord(Base):
    __tablename__ = 'leads'

    id: Mapped[int] = mapped_column(primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    raw_input: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(50), default=None)
    status: Mapped[str] = mapped_column(String(20))
    result_json: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(50))
    attempts: Mapped[int]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cost_usd: Mapped[float]
    latency_ms: Mapped[int]
    error: Mapped[str | None] = mapped_column(Text, default=None)
    sync_status: Mapped[str] = mapped_column(String(20), default='pending')
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )


def init_db():
    Base.metadata.create_all(engine)