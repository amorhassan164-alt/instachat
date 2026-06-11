from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from datetime import datetime, timezone
from database import Base


class Config(Base):
    __tablename__ = "config"

    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(Text, nullable=False, default="")
    page_id = Column(String(64), nullable=False, default="")
    instagram_account_id = Column(String(64), nullable=False, default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(String(64), nullable=False)
    post_caption = Column(Text, default="")
    post_thumbnail = Column(Text, default="")
    keywords = Column(Text, nullable=False)   # comma-separated
    comment_reply = Column(Text, nullable=False)
    dm_message = Column(Text, nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ProcessedComment(Base):
    __tablename__ = "processed_comments"

    id = Column(Integer, primary_key=True, index=True)
    comment_id = Column(String(64), unique=True, index=True, nullable=False)
    campaign_id = Column(Integer, nullable=False)
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
