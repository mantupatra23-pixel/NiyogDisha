from typing import Dict, Optional
from app.sources.adapters.ibps import IBPSAdapter
from app.sources.adapters.indiapost import IndiaPostAdapter
from app.sources.adapters.rrb import RRBAdapter
from app.sources.adapters.ssc import SSCAdapter
from app.sources.adapters.upsc import UPSCAdapter
from app.sources.base import BaseSourceAdapter


class AdapterRegistry:
    def __init__(self):
        self._adapters: Dict[str, BaseSourceAdapter] = {
            "ssc": SSCAdapter(),
            "upsc": UPSCAdapter(),
            "rrb": RRBAdapter(),
            "ibps": IBPSAdapter(),
            "indiapost": IndiaPostAdapter(),
        }

    def get_adapter(self, name: str) -> Optional[BaseSourceAdapter]:
        key = name.lower().replace("-", "").replace("_", "").strip()
        if key in ("indiapost", "india_post", "post"):
            key = "indiapost"
        return self._adapters.get(key)

    def list_adapters(self) -> Dict[str, BaseSourceAdapter]:
        return self._adapters

    async def close_all(self):
        for adapter in self._adapters.values():
            await adapter.close()


registry = AdapterRegistry()
