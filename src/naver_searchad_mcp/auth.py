from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import hmac
import os
import time


class MissingCredentialsError(RuntimeError):
    pass


@dataclass(frozen=True)
class NaverSearchAdCredentials:
    customer_id: str
    access_license: str
    secret_key: str

    @classmethod
    def from_env(cls) -> "NaverSearchAdCredentials":
        missing = [
            name
            for name in (
                "NAVER_SEARCHAD_CUSTOMER_ID",
                "NAVER_SEARCHAD_ACCESS_LICENSE",
                "NAVER_SEARCHAD_SECRET_KEY",
            )
            if not os.getenv(name)
        ]
        if missing:
            raise MissingCredentialsError(
                "Missing Naver SearchAd credential environment variable(s): " + ", ".join(missing)
            )
        return cls(
            customer_id=os.environ["NAVER_SEARCHAD_CUSTOMER_ID"],
            access_license=os.environ["NAVER_SEARCHAD_ACCESS_LICENSE"],
            secret_key=os.environ["NAVER_SEARCHAD_SECRET_KEY"],
        )


def current_timestamp_ms() -> str:
    return str(round(time.time() * 1000))


def generate_signature(timestamp: str, method: str, uri: str, secret_key: str) -> str:
    """Generate the official Naver SearchAd signature.

    Official sample signs: "{timestamp}.{method}.{uri}" with HMAC-SHA256 and
    returns the base64-encoded digest.
    """
    message = f"{timestamp}.{method.upper()}.{uri}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def build_headers(
    credentials: NaverSearchAdCredentials,
    *,
    method: str,
    uri: str,
    timestamp: str | None = None,
    content_type: str | None = "application/json; charset=UTF-8",
) -> dict[str, str]:
    timestamp = timestamp or current_timestamp_ms()
    headers = {
        "X-Timestamp": timestamp,
        "X-API-KEY": credentials.access_license,
        "X-Customer": str(credentials.customer_id),
        "X-Signature": generate_signature(timestamp, method, uri, credentials.secret_key),
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers
