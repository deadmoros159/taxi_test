import httpx
import logging
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


class MediaClient:
    def __init__(self):
        self.base_url = settings.MEDIA_SERVICE_URL
        self.client = httpx.AsyncClient(
            timeout=90.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            follow_redirects=True
        )

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        mime_type: str,
        tag: str = "PROFILE_PHOTO",
        token: Optional[str] = None
    ) -> Optional[Dict]:
        url = f"{self.base_url}/api/v1/media/upload"
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        files = {"file": (filename, file_data, mime_type)}
        data = {"tag": tag}

        for attempt in range(2):
            try:
                response = await self.client.post(
                    url, files=files, data=data, headers=headers, timeout=90.0
                )
                break
            except (httpx.ReadError, httpx.ConnectError) as e:
                if attempt == 0:
                    logger.warning(f"Media upload attempt {attempt + 1} failed: {e}, retrying...")
                else:
                    logger.error(f"Error uploading file to media-service: {e}", exc_info=True)
                    return None
            
        try:
            if response.status_code == 201:
                result = response.json()
                logger.info(f"File uploaded successfully: media_id={result.get('media_id')}")
                return result
            else:
                error_data = response.json() if response.content else {}
                logger.error(
                    f"Media service error: {response.status_code}, "
                    f"detail: {error_data.get('detail', 'Unknown error')}"
                )
                return None
        except Exception as e:
            logger.error(f"Error uploading file to media-service: {e}", exc_info=True)
            return None

    async def close(self):
        await self.client.aclose()

