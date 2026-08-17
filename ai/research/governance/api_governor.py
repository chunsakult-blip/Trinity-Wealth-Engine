from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class APIUsage:

    service: str
    requests: int
    limit: int


class APIGovernor:


    def __init__(
        self,
        daily_limit: int = 1000,
    ):

        self.daily_limit = daily_limit

        self.usage = 0

        self.date = (
            datetime.now()
            .date()
        )


    def allowed(
        self,
        requests: int = 1,
    ) -> bool:


        today = datetime.now().date()


        if today != self.date:

            self.date = today
            self.usage = 0


        if (
            self.usage + requests
            > self.daily_limit
        ):

            return False


        return True



    def consume(
        self,
        requests: int = 1,
    ):


        if not self.allowed(requests):

            raise RuntimeError(
                "API daily limit exceeded"
            )


        self.usage += requests



    def status(self):

        return APIUsage(
            service="SEC",
            requests=self.usage,
            limit=self.daily_limit,
        )
