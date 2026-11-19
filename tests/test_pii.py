import pytest

from app.pii import find_pii, redact_pii


#test that each PII type is detected
@pytest.mark.parametrize(
    "text, kind",
    [
        ("mail me at john.doe+test@example.co.uk", "EMAIL"),
        ("my ssn is 123-45-6789", "SSN"),
        ("call (555) 123-4567", "PHONE"),
        ("call +1 555.123.4567", "PHONE"),
        ("card 4111 1111 1111 1111", "CREDIT_CARD"),
    ],
)
def test_detects_pii(text, kind):
    assert kind in {m.kind for m in find_pii(text)}


#test that normal text has no PII
def test_clean_text_has_no_pii():
    assert find_pii("What is the capital of France?") == []


#test that every PII match is replaced with its label
def test_redact_replaces_every_match():
    text = "email john@example.com or call 555-123-4567"
    assert redact_pii(text, find_pii(text)) == "email [EMAIL] or call [PHONE]"


#test that overlapping matches don't leak PII (regression test for the overlap fix)
def test_overlapping_matches_do_not_leak():
    text = "(555) 123-4567john@x.com"
    assert redact_pii(text, find_pii(text)) == "[PHONE][EMAIL]"


#test that order numbers aren't flagged as phones (known limitation, expected to fail)
@pytest.mark.xfail(strict=True, reason="known limitation: any 10-digit number looks like a phone number")
def test_order_number_is_not_a_phone():
    assert find_pii("my order number is 1234567890") == []