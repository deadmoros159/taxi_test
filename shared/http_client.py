"""
HTTP клиент с Circuit Breaker и Retry Logic
"""
import httpx
import asyncio
from typing import Optional, Dict, Any
import logging

from shared.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from shared.retry import retry_with_backoff, RetryConfig

logger = logging.getLogger(__name__)


class ResilientHTTPClient:
    """
    HTTP клиент с защитой от сбоев:
    - Circuit Breaker
    - Retry с exponential backoff
    - Timeout handling
    """
    
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        circuit_breaker: Optional[CircuitBreaker] = None,
        retry_config: Optional[RetryConfig] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            name=f"http_client_{base_url}"
        )
        self.retry_config = retry_config or RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            max_delay=10.0
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Получить или создать HTTP клиент"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout
            )
        return self._client
    
    async def close(self):
        """Закрыть HTTP клиент"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _make_request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Выполнить HTTP запрос с retry"""
        client = await self._get_client()
        
        async def _request():
            return await client.request(method, path, **kwargs)
        
        # Retry выполняется внутри circuit breaker
        response = await retry_with_backoff(
            _request,
            self.retry_config
        )
        return response
    
    async def get(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """GET запрос"""
        async def _call():
            return await self._make_request("GET", path, headers=headers, **kwargs)
        
        return await self.circuit_breaker.call(_call)
    
    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """POST запрос"""
        async def _call():
            return await self._make_request("POST", path, json=json, headers=headers, **kwargs)
        
        return await self.circuit_breaker.call(_call)
    
    async def patch(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """PATCH запрос"""
        async def _call():
            return await self._make_request("PATCH", path, json=json, headers=headers, **kwargs)
        
        return await self.circuit_breaker.call(_call)
    
    async def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """PUT запрос"""
        async def _call():
            return await self._make_request("PUT", path, json=json, headers=headers, **kwargs)
        
        return await self.circuit_breaker.call(_call)
    
    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """DELETE запрос"""
        async def _call():
            return await self._make_request("DELETE", path, headers=headers, **kwargs)
        
        return await self.circuit_breaker.call(_call)
