from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional


class SECCache:
    """
    Local JSON cache for SEC Company Facts.

    Cache is intentionally dumb:
      - no transformation
      - no normalization
      - no financial calculations

    It stores the raw SEC payload only.
    """

    def __init__(
        self,
        directory: str | Path,
    ) -> None:

        self.directory = Path(
            directory
        )

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def normalize_cik(
        cik: str | int,
    ) -> str:

        digits = "".join(
            character
            for character in str(cik)
            if character.isdigit()
        )

        if not digits:
            raise ValueError(
                "CIK must contain digits"
            )

        return digits.zfill(10)

    def path_for(
        self,
        cik: str | int,
    ) -> Path:

        normalized = self.normalize_cik(cik)

        return (
            self.directory
            / f"CIK{normalized}.json"
        )

    def save(
        self,
        cik: str | int,
        payload: Mapping[str, Any],
    ) -> Path:

        path = self.path_for(cik)

        with path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
            )

        return path

    def load(
        self,
        cik: str | int,
    ) -> Optional[Mapping[str, Any]]:

        path = self.path_for(cik)

        if not path.exists():
            return None

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            payload = json.load(handle)

        if not isinstance(
            payload,
            Mapping,
        ):
            raise ValueError(
                "Cached SEC payload must be an object"
            )

        return payload

    def exists(
        self,
        cik: str | int,
    ) -> bool:

        return self.path_for(cik).exists()
