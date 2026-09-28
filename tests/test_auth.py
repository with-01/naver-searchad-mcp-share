import base64
import hashlib
import hmac

import pytest

from naver_searchad_mcp.auth import (
    MissingCredentialsError,
    NaverSearchAdCredentials,
    build_headers,
    generate_signature,
)


def test_generate_signature_matches_official_algorithm():
    timestamp = "1700000000000"
    method = "GET"
    uri = "/ncc/campaigns"
    secret = "test-secret"
    expected = base64.b64encode(
        hmac.new(secret.encode(), f"{timestamp}.{method}.{uri}".encode(), hashlib.sha256).digest()
    ).decode()
    assert generate_signature(timestamp, method, uri, secret) == expected


def test_build_headers_match_official_names():
    creds = NaverSearchAdCredentials(customer_id="123", access_license="license", secret_key="secret")
    headers = build_headers(creds, method="GET", uri="/ncc/campaigns", timestamp="1700000000000")
    assert headers["Content-Type"] == "application/json; charset=UTF-8"
    assert headers["X-Timestamp"] == "1700000000000"
    assert headers["X-API-KEY"] == "license"
    assert headers["X-Customer"] == "123"
    assert headers["X-Signature"]


def test_build_headers_can_omit_content_type_for_multipart_boundary():
    creds = NaverSearchAdCredentials(customer_id="123", access_license="license", secret_key="secret")
    headers = build_headers(
        creds,
        method="POST",
        uri="/api/tool/file/upload",
        timestamp="1700000000000",
        content_type=None,
    )
    assert "Content-Type" not in headers
    assert headers["X-API-KEY"] == "license"


def test_credentials_from_env_requires_all_fields(monkeypatch):
    for key in ["NAVER_SEARCHAD_CUSTOMER_ID", "NAVER_SEARCHAD_ACCESS_LICENSE", "NAVER_SEARCHAD_SECRET_KEY"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(MissingCredentialsError) as exc:
        NaverSearchAdCredentials.from_env()
    assert "NAVER_SEARCHAD_CUSTOMER_ID" in str(exc.value)
    assert "secret" not in str(exc.value).lower().replace("secret_key", "")


def test_credentials_from_env_loads_without_printing_values(monkeypatch):
    monkeypatch.setenv("NAVER_SEARCHAD_CUSTOMER_ID", "123")
    monkeypatch.setenv("NAVER_SEARCHAD_ACCESS_LICENSE", "license")
    monkeypatch.setenv("NAVER_SEARCHAD_SECRET_KEY", "secret")
    creds = NaverSearchAdCredentials.from_env()
    assert creds.customer_id == "123"
    assert creds.access_license == "license"
    assert creds.secret_key == "secret"
