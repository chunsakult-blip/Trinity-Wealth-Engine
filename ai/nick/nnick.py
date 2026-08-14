"""
Nick - Chief Investment Officer.

Nick is the final investment reasoning layer.

Nick should consume structured intelligence produced by the
research division rather than directly searching every source.
"""


class Nick:

    name = "Nick"
    role = "Chief Investment Officer"

    def evaluate(self, investment_package: dict) -> dict:
        return {
            "agent": self.name,
            "role": self.role,
            "status": "pending",
            "decision": None,
            "investment_package": investment_package,
        }
