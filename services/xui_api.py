import json
import logging
import secrets
import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import secrets
import string


import aiohttp

from config import settings

logger = logging.getLogger(__name__)

_JSON_OPTS: Dict[str, Any] = {"content_type": None}


@dataclass
class CreatedClient:
    email:    str
    uuid:     str
    sub_link: str
    sub_id:    str


@dataclass
class ClientInfo:
    email:          str
    uuid:           str
    total_gb:       float
    upload_bytes:   int
    download_bytes: int
    expiry_time:    Optional[datetime]
    enable:         bool

    @property
    def used_gb(self) -> float:
        return (self.upload_bytes + self.download_bytes) / (1024 ** 3)

    @property
    def remaining_gb(self) -> float:
        return max(0.0, self.total_gb - self.used_gb)

    @property
    def is_expired(self) -> bool:
        return self.expiry_time is not None and datetime.now() > self.expiry_time


class XUIClient:

    def __init__(self) -> None:
        self._session:    Optional[aiohttp.ClientSession] = None
        self._logged_in:  bool = False
        self.base_url:    str  = settings.XUI_BASE_URL.rstrip("/")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
            self._logged_in = False
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        session = await self._get_session()
        form = aiohttp.FormData()
        form.add_field("username", settings.XUI_USERNAME)
        form.add_field("password", settings.XUI_PASSWORD)
        try:
            async with session.post(
                f"{self.base_url}/login", data=form,
                timeout=aiohttp.ClientTimeout(total=15, connect=5),
            ) as resp:
                result = await resp.json(**_JSON_OPTS)
                if result.get("success"):
                    self._logged_in = True
                    logger.info("✅ XUI login OK")
                    return True
                logger.error("❌ XUI login failed: %s", result)
                return False
        except Exception as exc:
            logger.exception("XUI login error: %s", exc)
            return False

    async def _ensure_auth(self) -> bool:
        if not self._logged_in:
            return await self.login()
        return True

    async def _get(self, path: str, _retry: bool = True) -> Optional[Dict]:
        if not await self._ensure_auth():
            return None
        session = await self._get_session()
        try:
            async with session.get(
                f"{self.base_url}{path}",
                timeout=aiohttp.ClientTimeout(total=20, connect=5),
            ) as resp:
                if resp.status == 401 and _retry:
                    self._logged_in = False
                    if await self.login():
                        return await self._get(path, _retry=False)
                    return None
                return await resp.json(**_JSON_OPTS)
        except Exception as exc:
            logger.exception("XUI GET %s: %s", path, exc)
            return None

    async def _post(self, path: str, payload: Any, _retry: bool = True) -> Optional[Dict]:
        if not await self._ensure_auth():
            return None
        session = await self._get_session()
        
        custom_timeout = aiohttp.ClientTimeout(total=45, connect=10)
        
        try:
            async with session.post(
                f"{self.base_url}{path}",
                json=payload,
                timeout=custom_timeout,
            ) as resp:
                if resp.status == 401 and _retry:
                    self._logged_in = False
                    if await self.login():
                        return await self._post(path, payload, _retry=False)
                    return None
                return await resp.json(**_JSON_OPTS)
        except asyncio.TimeoutError:
            logger.error("⏳ TimeoutError directly caught in _post for %s", path)
            return None
        except Exception as exc:
            logger.exception("🚨 CRITICAL EXCEPTION IN _post FOR %s: %s", path, exc)
            return None


    async def get_inbounds(self) -> Optional[list]:
        data = await self._get("/panel/api/inbounds/list")
        return data.get("obj") if data and data.get("success") else None

    async def get_inbound(self, inbound_id: int) -> Optional[Dict]:
        data = await self._get(f"/panel/api/inbounds/get/{inbound_id}")
        return data.get("obj") if data and data.get("success") else None

    async def _get_existing_clients(self, inbound_id: int) -> List[Dict]:
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            logger.warning("Could not fetch inbound %s — starting with empty client list", inbound_id)
            return []

        raw = inbound.get("settings", "{}")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            return parsed.get("clients", [])
        except Exception as exc:
            logger.exception("Failed to parse inbound settings: %s", exc)
            return []

    async def add_client(
        self,
        inbound_id:    int,
        email:         str,
        data_limit_gb: float,
        duration_days: int,
    ) -> Optional[CreatedClient]:
        
        raw_key = secrets.token_bytes(32)
        client_password = base64.b64encode(raw_key).decode('utf-8')
        expiry_ms   = int((datetime.now() + timedelta(days=duration_days)).timestamp() * 1000)
        total_bytes = int(data_limit_gb * 1024 ** 3) if data_limit_gb > 0 else 0
        sub_id = self.generate_subid()
        print(sub_id)
        sub_link = self._make_sub_link(sub_id)

        new_client = {
            "subId":      sub_id,
            "password":   client_password,
            "email":      email,
            "totalGB":    total_bytes,
            "expiryTime": expiry_ms,
            "enable":     True,
            "tgId":       "",
            "limitIp":    0,
            "reset":      0,
            "alterId":    0
        }

        existing_clients = await self._get_existing_clients(inbound_id)
        for c in existing_clients:
            if c.get("email") == email:
                logger.error("Email %s already exists in inbound %s", email, inbound_id)
                return None

        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [new_client]})
        }

        result = await self._post("/panel/api/inbounds/addClient", payload)

        if not result or not result.get("success"):
            logger.error("❌ addClient failed for %s. Response: %s", email, result)
            return None

        logger.info("✅ Client added independently: email=%s", email)

        return CreatedClient(
            email=email,
            uuid=client_password,
            sub_link=sub_link,
            sub_id=sub_id
        )


    async def get_client_info(self, email: str) -> Optional[ClientInfo]:
        data = await self._get(f"/panel/api/inbounds/getClientTraffics/{email}")
        if not data or not data.get("success"):
            return None
        obj = data.get("obj")
        if not obj:
            return None
        expiry_ts   = obj.get("expiryTime", 0)
        total_bytes = obj.get("total", 0)
        return ClientInfo(
            email=obj.get("email", email),
            uuid=obj.get("id", ""),
            total_gb=total_bytes / (1024 ** 3) if total_bytes > 0 else 0.0,
            upload_bytes=obj.get("up", 0),
            download_bytes=obj.get("down", 0),
            expiry_time=datetime.fromtimestamp(expiry_ts / 1000) if expiry_ts > 0 else None,
            enable=obj.get("enable", True),
        )

    def _make_sub_link(self, sub_id: str) -> str:
        path = settings.SUB_PATH.rstrip("/") + "/"
        return f"{settings.SUB_DOMAIN}:{settings.SUB_PORT}{path}{sub_id}"

    def generate_subid(self, length: int = 16) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))



xui_client = XUIClient()