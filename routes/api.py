
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from instagram import InstagramClient
from models import Campaign, Config

router = APIRouter(prefix="/api")


# ── Schemas ──────────────────────────────────────────────────────────────────

class ConfigIn(BaseModel):
    access_token: str
    page_id: str
    instagram_account_id: str


class ConfigOut(BaseModel):
    page_id: str
    instagram_account_id: str
    has_token: bool


class CampaignIn(BaseModel):
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    active: bool = True


class CampaignOut(BaseModel):
    id: int
    post_id: str
    post_caption: str
    post_thumbnail: str
    keywords: str
    comment_reply: str
    dm_message: str
    active: bool
    created_at: str


# ── Config endpoints ──────────────────────────────────────────────────────────

@router.get("/config", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        return ConfigOut(page_id="", instagram_account_id="", has_token=False)
    return ConfigOut(
        page_id=config.page_id,
        instagram_account_id=config.instagram_account_id,
        has_token=bool(config.access_token),
    )


@router.post("/config")
async def save_config(body: ConfigIn, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config:
        config = Config()
        db.add(config)
    config.access_token = body.access_token
    config.page_id = body.page_id
    config.instagram_account_id = body.instagram_account_id
    config.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Quick token validation
    client = InstagramClient(body.access_token)
    uid = await client.verify_token()
    if not uid:
        return {"status": "saved", "warning": "Token may be invalid — API call failed"}
    return {"status": "saved", "instagram_id": uid}


# ── Campaign endpoints ────────────────────────────────────────────────────────

def _serialize(c: Campaign) -> dict:
    return {
        "id": c.id,
        "post_id": c.post_id,
        "post_caption": c.post_caption or "",
        "post_thumbnail": c.post_thumbnail or "",
        "keywords": c.keywords,
        "comment_reply": c.comment_reply,
        "dm_message": c.dm_message,
        "active": c.active,
        "created_at": c.created_at.isoformat() if c.created_at else "",
    }


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return [_serialize(c) for c in db.query(Campaign).order_by(Campaign.id.desc()).all()]


@router.post("/campaigns")
async def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    thumbnail, caption = "", ""
    if config and config.access_token:
        client = InstagramClient(config.access_token)
        details = await client.get_post_details(body.post_id)
        if not details.get("error"):
            thumbnail = details["thumbnail"]
            caption = details["caption"]

    campaign = Campaign(
        post_id=body.post_id,
        post_caption=caption,
        post_thumbnail=thumbnail,
        keywords=body.keywords,
        comment_reply=body.comment_reply,
        dm_message=body.dm_message,
        active=body.active,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _serialize(campaign)


@router.put("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: int, body: CampaignIn, db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    # Re-fetch post details if post_id changed
    if campaign.post_id != body.post_id:
        config = db.query(Config).first()
        if config and config.access_token:
            client = InstagramClient(config.access_token)
            details = await client.get_post_details(body.post_id)
            if not details.get("error"):
                campaign.post_thumbnail = details["thumbnail"]
                campaign.post_caption = details["caption"]

    campaign.post_id = body.post_id
    campaign.keywords = body.keywords
    campaign.comment_reply = body.comment_reply
    campaign.dm_message = body.dm_message
    campaign.active = body.active
    db.commit()
    return _serialize(campaign)


@router.patch("/campaigns/{campaign_id}/toggle")
def toggle_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    campaign.active = not campaign.active
    db.commit()
    return {"id": campaign.id, "active": campaign.active}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).get(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    db.delete(campaign)
    db.commit()
    return {"deleted": True}


@router.get("/campaigns/{campaign_id}/post-preview")
async def post_preview(campaign_id: Optional[str] = None, post_id: str = "", db: Session = Depends(get_db)):
    """Fetch live post thumbnail + caption for a given post ID."""
    config = db.query(Config).first()
    if not config or not config.access_token:
        raise HTTPException(400, "Instagram credentials not configured")
    client = InstagramClient(config.access_token)
    details = await client.get_post_details(post_id)
    if details.get("error"):
        raise HTTPException(400, details["error"].get("message", "Failed to fetch post"))
    return details


@router.get("/post-preview")
async def post_preview_standalone(post_id: str, db: Session = Depends(get_db)):
    config = db.query(Config).first()
    if not config or not config.access_token:
        raise HTTPException(400, "Instagram credentials not configured")
    client = InstagramClient(config.access_token)
    details = await client.get_post_details(post_id)
    if details.get("error"):
        raise HTTPException(400, details["error"].get("message", "Failed to fetch post"))
    return details
