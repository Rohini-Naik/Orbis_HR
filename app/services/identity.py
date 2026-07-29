"""Company email addresses.

An employee's company address is their login identity, so it must be unique and
reproducible. Names cannot carry that load on their own — this dataset has 1,200
distinct names across ~100,000 people, with one name shared by 112 of them — so
a numeric suffix is added whenever a slug is already taken.
"""
import re
import unicodedata
from typing import Callable, Optional

from rag_engine import settings


def slugify_name(full_name: str) -> str:
    """'Priya  Rao' -> 'priya.rao'. Accents are folded, punctuation dropped."""
    ascii_name = (
        unicodedata.normalize("NFKD", full_name or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    parts = re.findall(r"[a-z0-9]+", ascii_name.lower())
    return ".".join(parts) or "employee"


def build_email(local_part: str, domain: Optional[str] = None) -> str:
    return f"{local_part}@{domain or settings.COMPANY_EMAIL_DOMAIN}"


def generate_email(
    full_name: str,
    is_taken: Callable[[str], bool],
    domain: Optional[str] = None,
) -> str:
    """Mint the first free address for this name: `priya.rao@`, then
    `priya.rao2@`, `priya.rao3@` … exactly how real employers disambiguate.

    `is_taken` is supplied by the caller so the same logic serves both the bulk
    backfill (checking an in-memory set) and single inserts (checking the DB).
    """
    base = slugify_name(full_name)
    candidate = build_email(base, domain)
    suffix = 1
    while is_taken(candidate):
        suffix += 1
        candidate = build_email(f"{base}{suffix}", domain)
    return candidate
