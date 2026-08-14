"""
Challenge Agent / Devil's Advocate.

Its job is to attack an investment thesis rather than confirm it.
"""


class ChallengeAgent:

    name = "Challenge Agent"

    def challenge(self, thesis: dict) -> dict:
        return {
            "agent": self.name,
            "status": "pending",
            "thesis": thesis,
            "counter_arguments": [],
        }
