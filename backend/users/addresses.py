import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import connection

EMAIL_MAX_LENGTH = 254
ADDRESS_LOCK_CLASS = 7301


def clean_address(raw) -> str | None:
    value = unicodedata.normalize("NFKC", str(raw or "")).strip()
    local, at, domain = value.rpartition("@")
    if not at or not local or not domain or domain.startswith("["):
        return None
    try:
        domain = domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    email = f"{local}@{domain}"
    if "." not in domain or not email.isascii() or len(email) > EMAIL_MAX_LENGTH:
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def address_variants(email: str) -> set[str]:
    local, _, domain = email.rpartition("@")
    try:
        shown = domain.encode("ascii").decode("idna")
    except UnicodeError:
        shown = domain
    return {email, f"{local}@{shown}"}


def lock_address(email: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s, hashtext(%s))", [ADDRESS_LOCK_CLASS, email.lower()])
