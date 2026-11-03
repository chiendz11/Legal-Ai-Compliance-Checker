import pytest
from legal_checker.modules.accounts.security import SessionSigner, hash_password, verify_password

SECRET = "s" * 40


def test_password_hash_verifies_and_is_salted():
    first, second = hash_password("correct horse"), hash_password("correct horse")
    assert first != second and first.startswith("scrypt$")
    assert verify_password("correct horse", first)
    assert not verify_password("wrong horse", first)
    assert not verify_password("correct horse", "garbage")


def test_short_passwords_and_weak_secrets_are_rejected():
    with pytest.raises(ValueError):
        hash_password("short")
    with pytest.raises(ValueError):
        SessionSigner("too-short", 60)


def test_session_token_round_trip_expiry_and_tampering():
    signer = SessionSigner(SECRET, ttl_seconds=60)
    token = signer.issue("user1", now=1000)
    assert signer.verify(token, now=1030) == "user1"
    assert signer.verify(token, now=1061) is None  # expired
    body, signature = token.split(".")
    forged = SessionSigner("x" * 40, 60).issue("admin", now=1000).split(".")[0]
    assert signer.verify(f"{forged}.{signature}", now=1030) is None
    assert signer.verify(f"{body}.AAAA", now=1030) is None
    assert signer.verify("not-a-token", now=1030) is None
