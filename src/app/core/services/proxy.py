from mm_base6 import Service
from mm_concurrency import async_synchronized
from mm_http import http_request
from mm_std import utc_now

from app.core.types import AppCore


class ProxyService(Service):
    core: AppCore

    @async_synchronized
    async def update(self) -> int:
        res = await http_request(self.core.settings.proxies_url)
        if res.is_err():
            await self.core.event("update_proxies", {"response": res.to_dict()})
            return -1
        proxies = (res.body or "").strip().splitlines()
        proxies = [p.strip() for p in proxies if p.strip()]
        self.core.state.proxies = proxies
        self.core.state.proxies_updated_at = utc_now()
        return len(proxies)
