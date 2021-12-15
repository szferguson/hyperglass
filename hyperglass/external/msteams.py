"""Session handler for Microsoft Teams API."""

import typing as t

# Project
from hyperglass.log import log
from hyperglass.external._base import BaseExternal
from hyperglass.models.webhook import Webhook

if t.TYPE_CHECKING:
    from hyperglass.models.config.logging import Http


class MSTeams(BaseExternal, name="MSTeams"):
    """Microsoft Teams session handler."""

    def __init__(self: "MSTeams", config: "Http") -> None:
        """Initialize external base class with Microsoft Teams connection details."""

        super().__init__(base_url="https://outlook.office.com", config=config, parse=False)

    async def send(self: "MSTeams", query: t.Dict[str, t.Any]):
        """Send an incoming webhook to Microsoft Teams."""

        payload = Webhook(**query)

        log.debug("Sending query data to Microsoft Teams:\n{}", payload)

        return await self._apost(endpoint=self.config.host.path, data=payload.msteams())
