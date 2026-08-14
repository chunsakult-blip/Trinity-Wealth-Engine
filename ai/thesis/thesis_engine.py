"""
Investment Thesis Engine.
"""


class ThesisEngine:

    name = "Thesis Engine"

    def build(self, company_data: dict) -> dict:
        return {
            "agent": self.name,
            "status": "pending",
            "bull_thesis": [],
            "bear_thesis": [],
            "company": company_data,
        }
