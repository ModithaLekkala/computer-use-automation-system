from src.policy.redaction import redact
def test_redaction():
    x=redact({"token":"abc","note":"SSN 123-45-6789"}); assert x["token"]=="[REDACTED]" and "123-45-6789" not in x["note"]
