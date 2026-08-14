"""
Fact Verifier.

Validates evidence before it enters institutional knowledge.
"""


class FactVerifier:

    name = "Fact Verifier"

    def verify(self, evidence: dict) -> dict:
        return {
            "agent": self.name,
            "status": "pending",
            "verified": False,
            "evidence": evidence,
        }
