import httpx
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("instagram")

BASE_URL = "https://graph.facebook.com/v19.0"


class InstagramClient:
    def __init__(self, access_token: str):
        self.access_token = access_token

    def _headers(self):
        return {"Content-Type": "application/json"}

    async def _request(
        self,
        method: str,
        path: str,
        retries: int = 3,
        **kwargs,
    ) -> dict:
        url = f"{BASE_URL}/{path}"
        params = kwargs.pop("params", {})
        params["access_token"] = self.access_token

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.request(
                        method, url, params=params, **kwargs
                    )
                data = resp.json()
                logger.info("IG API %s %s → %s", method, path, resp.status_code)

                # Rate limit handling
                if resp.status_code == 429 or (
                    isinstance(data, dict)
                    and data.get("error", {}).get("code") in (4, 17, 32, 613)
                ):
                    wait = 2 ** (attempt + 1)
                    logger.warning("Rate limited. Retrying in %ss…", wait)
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code >= 400:
                    logger.error("IG API error: %s", data)

                return data
            except httpx.RequestError as exc:
                logger.error("Request error on attempt %d: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return {"error": {"message": "Max retries exceeded"}}

    async def reply_to_comment(self, comment_id: str, message: str) -> dict:
        """Post a public reply to a comment."""
        return await self._request(
            "POST",
            f"{comment_id}/replies",
            json={"message": message},
        )

    async def send_dm(self, instagram_user_id: str, message: str) -> dict:
        """Send a private DM to a user. Requires instagram_manage_messages."""
        # The recipient must have messaged the business first OR permission approved.
        # We send via the Instagram Messaging API.
        return await self._request(
            "POST",
            "me/messages",
            json={
                "recipient": {"id": instagram_user_id},
                "message": {"text": message},
            },
        )

    async def get_post_details(self, post_id: str) -> dict:
        """Fetch post thumbnail URL and caption."""
        data = await self._request(
            "GET",
            post_id,
            params={"fields": "caption,media_url,thumbnail_url,media_type"},
        )
        return {
            "caption": data.get("caption", ""),
            "thumbnail": data.get("thumbnail_url") or data.get("media_url", ""),
            "media_type": data.get("media_type", ""),
            "error": data.get("error"),
        }

    async def verify_token(self) -> Optional[str]:
        """Returns the Instagram account ID if token is valid, else None."""
        data = await self._request("GET", "me", params={"fields": "id,name"})
        if "error" in data:
            return None
        return data.get("id")
