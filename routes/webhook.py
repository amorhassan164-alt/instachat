
import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from database import get_db
from instagram import InstagramClient
from models import Campaign, Config, ProcessedComment

router = APIRouter()
logger = logging.getLogger("webhook")

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "changeme")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")


def _verify_signature(body: bytes, signature_header: str) -> bool:
    """Validate X-Hub-Signature-256 against FACEBOOK_APP_SECRET."""
    if not APP_SECRET:
        logger.warning("APP_SECRET not set — skipping signature validation")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(
        APP_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)


@router.get("/webhook/instagram")
async def webhook_verify(request: Request):
    """Facebook webhook verification challenge.
    Facebook sends hub.mode, hub.verify_token, hub.challenge (dot-notation).
    """
    p = request.query_params
    mode      = p.get("hub.mode")
    token     = p.get("hub.verify_token")
    challenge = p.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        logger.info("Webhook verified ✓")
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/instagram")
async def webhook_receive(request: Request, db: Session = Depends(get_db)):
    """Receive and process Instagram comment events."""
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    payload = await request.json()
    logger.debug("Webhook payload: %s", payload)

    # Load config
    config: Config = db.query(Config).first()
    if not config or not config.access_token:
        logger.warning("No Instagram config found — ignoring webhook")
        return {"status": "ok"}

    client = InstagramClient(config.access_token)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            _handle_comment(value, db, client)

    return {"status": "ok"}


def _handle_comment(value: dict, db: Session, client: InstagramClient):
    """Fire-and-forget comment handling (sync wrapper for async calls)."""
    import asyncio

    comment_id = value.get("id")
    post_id = value.get("media", {}).get("id") or value.get("media_id")
    commenter_id = value.get("from", {}).get("id")
    text = (value.get("text") or "").lower()

    if not comment_id or not post_id:
        return

    # Deduplication
    if db.query(ProcessedComment).filter_by(comment_id=comment_id).first():
        logger.info("Comment %s already processed — skipping", comment_id)
        return

    # Find matching active campaign
    campaigns = db.query(Campaign).filter_by(active=True).all()
    matched: Campaign = None
    for campaign in campaigns:
        if campaign.post_id != post_id:
            continue
        for kw in (k.strip().lower() for k in campaign.keywords.split(",")):
            if kw and kw in text:
                matched = campaign
                break
        if matched:
            break

    if not matched:
        return

    logger.info(
        "Comment %s matched campaign %s — triggering reply + DM",
        comment_id,
        matched.id,
    )

    # Mark as processed immediately to prevent race conditions
    db.add(ProcessedComment(comment_id=comment_id, campaign_id=matched.id))
    db.commit()

    async def _send():
        await client.reply_to_comment(comment_id, matched.comment_reply)
        if commenter_id:
            await client.send_dm(commenter_id, matched.dm_message)

    asyncio.create_task(_send())
