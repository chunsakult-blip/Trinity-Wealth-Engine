"""
Reflection Agent.

Reviews the quality of the investment reasoning before Nick receives it.
"""


class ReflectionAgent:

    name = "Reflection Agent"

    def review(self, analysis: dict) -> dict:
        return {
            "agent": self.name,
            "status": "pending",
            "issues": [],
            "missing_information": [],
            "biases": [],
            "confidence": None,
            "analysis": analysis,
        }
