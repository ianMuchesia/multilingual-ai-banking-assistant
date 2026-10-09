"""Transaction references: prefix + 8 random upper-case letters/digits, e.g. BY4K7Q2M9X."""

import secrets
import string

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from bankchat.db.models import Transaction

ALPHABET = string.ascii_uppercase + string.digits
RANDOM_PART_LENGTH = 8
MAX_ATTEMPTS = 5


def random_reference(prefix: str) -> str:
    return prefix + "".join(secrets.choice(ALPHABET) for _ in range(RANDOM_PART_LENGTH))


def new_unique_reference(session: Session, prefix: str) -> str:
    for _ in range(MAX_ATTEMPTS):
        reference = random_reference(prefix)
        if not session.scalar(select(exists().where(Transaction.reference == reference))):
            return reference
    raise RuntimeError("could not generate a unique transaction reference")
