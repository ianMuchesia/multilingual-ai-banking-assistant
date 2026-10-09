"""Seed the database with fictional customers and ~6 months of history. DEV ONLY.

    python -m bankchat.db.seed            # create tables, seed if empty (idempotent)
    python -m bankchat.db.seed --reset    # DROP all tables first, then seed

Test users amina / brian / wanjiku share the dev-only password from SEED_DEV_PASSWORD
(default "password123"). Never point this at a database with real customers.
"""

import argparse
import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from bankchat.clock import utc_now
from bankchat.db.models import Account, Transaction, User
from bankchat.db.seed_data import OTHER_CUSTOMERS, TEST_CUSTOMERS, CustomerProfile, current_number, savings_number
from bankchat.db.seed_generator import generate_events, post_events
from bankchat.db.session import create_schema, drop_schema, make_engine, make_session_factory
from bankchat.domain import AccountType
from bankchat.logging_config import configure_logging
from bankchat.services.auth import hash_password
from bankchat.settings import Settings, get_settings

log = logging.getLogger(__name__)

SENTINEL_USERNAME = TEST_CUSTOMERS[0].username


def is_seeded(session: Session) -> bool:
    return session.scalar(select(User.id).where(User.username == SENTINEL_USERNAME)) is not None


def _create_customer(session: Session, profile: CustomerProfile, settings: Settings) -> list[Account]:
    password_hash = hash_password(settings.seed_dev_password, settings.bcrypt_rounds) if profile.can_login else None
    user = User(username=profile.username, full_name=profile.full_name, phone=profile.phone, password_hash=password_hash)
    session.add(user)
    session.flush()
    accounts = [Account(user_id=user.id, number=current_number(profile.index), type=AccountType.CURRENT.value,
                        currency=settings.currency, balance=Decimal(0))]
    if profile.has_savings:
        accounts.insert(0, Account(user_id=user.id, number=savings_number(profile.index),
                                   type=AccountType.SAVINGS.value, currency=settings.currency, balance=Decimal(0)))
    session.add_all(accounts)
    session.flush()
    return accounts


def seed_database(session: Session, settings: Settings, now: datetime | None = None) -> bool:
    """Seed once. Returns False (and changes nothing) if the data is already there."""
    if is_seeded(session):
        log.info("seed: already seeded (user %r exists), nothing to do", SENTINEL_USERNAME)
        return False
    now = now or utc_now()
    customers = TEST_CUSTOMERS + OTHER_CUSTOMERS
    accounts = {a.number: a for p in customers for a in _create_customer(session, p, settings)}

    events = generate_events(
        customers,
        customers,
        seed=settings.seed_random_seed,
        months=settings.seed_history_months,
        today=now.astimezone(settings.bank_timezone).date(),
        tz=settings.bank_timezone,
        now=now,
    )
    posted, balances = post_events(
        events, {number: Decimal(0) for number in accounts},
        seed=settings.seed_random_seed, reference_prefix=settings.reference_prefix,
    )
    session.add_all(
        Transaction(
            reference=p.reference,
            account_id=accounts[p.leg.account_number].id,
            direction=p.leg.direction.value,
            amount=p.leg.amount,
            channel=p.leg.channel.value,
            counterparty=p.leg.counterparty,
            description=p.leg.description,
            created_at=p.when,
            balance_after=p.balance_after,
        )
        for p in posted
    )
    for number, balance in balances.items():
        accounts[number].balance = balance
    session.commit()
    log.info("seed: %d customers, %d accounts, %d transactions", len(customers), len(accounts), len(posted))
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Benki Yetu demo database (DEV ONLY).")
    parser.add_argument("--reset", action="store_true", help="drop all tables before seeding")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    if args.reset:
        log.warning("seed: --reset, dropping all tables")
        drop_schema(engine)
    create_schema(engine)
    with make_session_factory(engine)() as session:
        seed_database(session, settings)
    engine.dispose()


if __name__ == "__main__":
    main()
