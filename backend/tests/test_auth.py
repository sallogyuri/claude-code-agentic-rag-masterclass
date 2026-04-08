import jwt as pyjwt
import auth as auth_module

# PyJWT's HS256 decode accepts a plain string key directly.
# The real PyJWKClient returns a PyJWKClientKey object, but jwt.decode
# also accepts a raw str/bytes for symmetric algorithms, which is simpler to mock.
SECRET = "test-hs256-secret-that-is-long-enough"


def _make_token(payload: dict) -> str:
    return pyjwt.encode(payload, SECRET, algorithm="HS256")


def test_missing_auth_header_returns_401(raw_client):
    """HTTPBearer returns 401 when Authorization header is absent."""
    response = raw_client.get("/chat/threads")
    assert response.status_code == 401


def test_expired_token_returns_401(raw_client, mock_jwks, monkeypatch):
    """A token with exp=1 (year 1970) must be rejected with 401."""
    token = _make_token({"sub": "user-id", "exp": 1})
    # Return the raw secret string — PyJWT accepts str for HS256 decode
    mock_jwks.get_signing_key_from_jwt.return_value = SECRET
    monkeypatch.setattr(auth_module, "_jwks_client", mock_jwks)

    response = raw_client.get(
        "/chat/threads",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_valid_token_grants_access(raw_client, mock_jwks, mock_supabase, monkeypatch):
    """A well-formed HS256 token with a future exp passes auth and hits the route."""
    import time

    token = _make_token({"sub": "user-id", "email": "u@test.com", "exp": int(time.time()) + 3600})
    mock_jwks.get_signing_key_from_jwt.return_value = SECRET
    monkeypatch.setattr(auth_module, "_jwks_client", mock_jwks)

    # Supabase threads query returns empty list
    (
        mock_supabase.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
        .data
    ) = []

    response = raw_client.get(
        "/chat/threads",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
