import asyncio
import datetime
from typing import Any, Callable
import logging as log

import aiohttp
from hass_client import HomeAssistantClient as HassClient
from hass_client.exceptions import (
    AuthenticationFailed,
    CannotConnect,
    ConnectionFailed,
    NotConnected,
)

from models.exceptions import ServiceTimeoutError


class HomeAssistantClient:
    session: aiohttp.ClientSession
    client: HassClient
    unknown_entities: set[str] = set()
    called_services: dict[int, datetime.datetime]
    on_connection_callbacks: list[Callable]

    def __init__(self, url, token):
        """Initialize the Client class."""

        self.url = url
        self.token = token
        self.called_services = {}
        self.on_connection_callbacks = []

    def register_on_connection(self, callback: Callable):
        """Register a callback to run when connected."""

        self.on_connection_callbacks.append(callback)

    async def connect(self):
        """Enter the Client class."""

        self.client = HassClient(
            self.url,
            self.token,
        )

        while not self.client.connected:
            try:
                await self.client.connect()
                log.info("Connected to Home Assistant")
            except (
                NotConnected,
                CannotConnect,
                ConnectionFailed,
            ):
                log.error("Not connected to Home Assistant, retrying in 5 seconds")
                await asyncio.sleep(5)
            except AuthenticationFailed:
                log.error("Authentication failed")
                break

        await self.on_connected()

    async def on_connected(self):
        """Run when connected to Home Assistant."""

        for callback in self.on_connection_callbacks:
            await callback()

    async def subscribe_events(self, on_event_callback: Callable) -> Callable:
        """Subscribe to events."""

        return await self.client.subscribe_events(on_event_callback)

    async def send_command(
            self, command: str, **kwargs: dict[str, Any]
    ):
        return await self.client.send_command(command, **kwargs)

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        target: dict[str, Any] | None = None,
        timeout: datetime.timedelta | None = None,
    ):
        """Call a service."""

        arg_hash = hash(
            (
                domain,
                service,
                frozenset(service_data) if service_data is not None else None,
                frozenset(target) if target is not None else None,
            )
        )

        if arg_hash in self.called_services:
            if self.called_services[arg_hash] > datetime.datetime.now():
                raise ServiceTimeoutError(
                    f"Service {domain}.{service} was called too recently"
                )

            del self.called_services[arg_hash]

        await self.client.call_service(domain, service, service_data, target)

        if timeout is not None:
            self.called_services[arg_hash] = datetime.datetime.now() + timeout