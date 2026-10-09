"""Deterministic transaction history for the seed customers.

Each customer gets their own random.Random seeded from (seed, username), so the same
anchor date always produces the same history. Events from all customers are applied in
time order with running balances; an event that would overdraw an account is skipped.
"""

import random
import string
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from decimal import Decimal

from bankchat.db.seed_data import (
    MPESA_CONTACTS,
    PESALINK_PAYEES,
    RENT_PAYBILL,
    TILLS,
    UTILITY_PAYBILLS,
    CustomerProfile,
    current_number,
    savings_number,
)
from bankchat.domain import Channel, Direction
from bankchat.slots.dates import add_months

SALARY_DAY = 25
SAVINGS_SWEEP_DAY = 26
RENT_DAYS = (1, 2, 3)
TILLS_PER_MONTH = (8, 14)
MPESA_OUT_PER_MONTH = (3, 6)
MPESA_IN_PER_MONTH = (1, 2)
MPESA_OUT_RANGE = (300, 7_000)
MPESA_IN_RANGE = (500, 5_000)
PESALINK_CHANCE = 0.5
PESALINK_RANGE = (5_000, 30_000)
PEER_TRANSFER_CHANCE = 0.5
PEER_TRANSFER_RANGE = (1_000, 10_000)
CASH_DEPOSIT_CHANCE = 0.25
CASH_DEPOSIT_RANGE = (2_000, 20_000)
AMOUNT_STEP = 10
FIRST_HOUR, LAST_HOUR = 7, 21
REFERENCE_CHARS = string.ascii_uppercase + string.digits
REFERENCE_RANDOM_LENGTH = 8


@dataclass(frozen=True)
class Leg:
    account_number: str
    direction: Direction
    amount: Decimal
    channel: Channel
    counterparty: str
    description: str


@dataclass(frozen=True)
class SeedEvent:
    when: datetime          # UTC
    legs: tuple[Leg, ...]   # one leg, or two for an internal transfer (out first)
    rng_key: str            # for a deterministic reference


@dataclass(frozen=True)
class PostedLeg:
    leg: Leg
    when: datetime
    reference: str
    balance_after: Decimal


class _CustomerHistory:
    """Builds one customer's events month by month."""

    def __init__(self, profile: CustomerProfile, others: tuple[CustomerProfile, ...], seed: str,
                 tz: tzinfo, now: datetime) -> None:
        self.p = profile
        self.others = others
        self.rng = random.Random(f"{seed}:{profile.username}")
        self.tz = tz
        self.now = now
        self.current = current_number(profile.index)
        self.savings = savings_number(profile.index)
        self.events: list[SeedEvent] = []

    def _at(self, day: date) -> datetime | None:
        moment = datetime.combine(
            day, time(self.rng.randint(FIRST_HOUR, LAST_HOUR), self.rng.randint(0, 59)), tzinfo=self.tz
        ).astimezone(timezone.utc)
        return moment if moment < self.now else None

    def _amount(self, low: int, high: int) -> Decimal:
        if low >= high:
            return Decimal(low)
        return Decimal(self.rng.randrange(low, high + 1, AMOUNT_STEP) if high - low >= AMOUNT_STEP else low)

    def _add(self, day: date, *legs: Leg) -> None:
        when = self._at(day)
        if when is not None:
            self.events.append(SeedEvent(when, legs, f"{self.p.username}:{len(self.events)}"))

    def _random_day(self, month_start: date) -> date:
        last = (add_months(month_start, 1) - timedelta(days=1)).day
        return month_start.replace(day=self.rng.randint(1, last))

    def opening(self, start: date) -> None:
        self._add(start, Leg(self.current, Direction.IN, Decimal(self.p.current_opening), Channel.DEPOSIT,
                             "Cash deposit", "Opening deposit"))
        if self.p.has_savings and self.p.savings_opening:
            self._add(start, Leg(self.savings, Direction.IN, Decimal(self.p.savings_opening), Channel.DEPOSIT,
                                 "Cash deposit", "Opening deposit"))

    def month(self, month_start: date) -> None:
        if not self.p.can_login:
            return
        self._salary_and_sweep(month_start)
        self._rent_and_utilities(month_start)
        self._everyday(month_start)
        self._occasional(month_start)

    def _salary_and_sweep(self, month_start: date) -> None:
        if not self.p.monthly_salary:
            return
        payday = month_start.replace(day=SALARY_DAY)
        self._add(payday, Leg(self.current, Direction.IN, Decimal(self.p.monthly_salary), Channel.SALARY,
                              self.p.employer or "Employer", f"Salary {payday:%b %Y}"))
        sweep = Decimal(round(self.p.monthly_salary * self.p.savings_rate, -2))
        if sweep and self.p.has_savings:
            self._add(
                month_start.replace(day=SAVINGS_SWEEP_DAY),
                Leg(self.current, Direction.OUT, sweep, Channel.INTERNAL,
                    f"Own savings account ****{self.savings[-4:]}", "Transfer to own savings"),
                Leg(self.savings, Direction.IN, sweep, Channel.INTERNAL,
                    f"Own current account ****{self.current[-4:]}", "Transfer from own current"),
            )

    def _rent_and_utilities(self, month_start: date) -> None:
        if self.p.monthly_rent:
            name, paybill, account = RENT_PAYBILL
            account = account.format(index=self.p.index)
            self._add(month_start.replace(day=self.rng.choice(RENT_DAYS)),
                      Leg(self.current, Direction.OUT, Decimal(self.p.monthly_rent), Channel.PAYBILL,
                          f"{name} (Paybill {paybill})", f"Rent, account {account}"))
        for name, paybill, account, low, high in UTILITY_PAYBILLS:
            account = account.format(index=self.p.index)
            self._add(self._random_day(month_start),
                      Leg(self.current, Direction.OUT, self._amount(low, high), Channel.PAYBILL,
                          f"{name} (Paybill {paybill})", f"Bill payment, account {account}"))

    def _everyday(self, month_start: date) -> None:
        for _ in range(self.rng.randint(*TILLS_PER_MONTH)):
            name, till, low, high = self.rng.choice(TILLS)
            self._add(self._random_day(month_start),
                      Leg(self.current, Direction.OUT, self._amount(low, high), Channel.TILL,
                          f"{name} (Till {till})", "Lipa na M-Pesa Buy Goods"))
        for _ in range(self.rng.randint(*MPESA_OUT_PER_MONTH)):
            name, phone = self.rng.choice(MPESA_CONTACTS)
            self._add(self._random_day(month_start),
                      Leg(self.current, Direction.OUT, self._amount(*MPESA_OUT_RANGE), Channel.MPESA,
                          f"{name} {phone}", f"Bank to M-Pesa {phone}"))
        for _ in range(self.rng.randint(*MPESA_IN_PER_MONTH)):
            name, phone = self.rng.choice(MPESA_CONTACTS)
            self._add(self._random_day(month_start),
                      Leg(self.current, Direction.IN, self._amount(*MPESA_IN_RANGE), Channel.MPESA,
                          f"{name} {phone}", "M-Pesa to bank"))

    def _occasional(self, month_start: date) -> None:
        if self.rng.random() < PESALINK_CHANCE:
            bank, name, account = self.rng.choice(PESALINK_PAYEES)
            label = bank.upper() if len(bank) <= 4 else bank.title()
            self._add(self._random_day(month_start),
                      Leg(self.current, Direction.OUT, self._amount(*PESALINK_RANGE), Channel.PESALINK,
                          f"{name} {label} a/c {account}", f"PesaLink to {label} a/c {account}"))
        if self.others and self.rng.random() < PEER_TRANSFER_CHANCE:
            peer = self.rng.choice(self.others)
            peer_account = current_number(peer.index)
            amount = self._amount(*PEER_TRANSFER_RANGE)
            self._add(self._random_day(month_start),
                      Leg(self.current, Direction.OUT, amount, Channel.INTERNAL,
                          f"{peer.full_name} ****{peer_account[-4:]}", f"Transfer to {peer.full_name}"),
                      Leg(peer_account, Direction.IN, amount, Channel.INTERNAL,
                          self.p.full_name, f"Transfer from {self.p.full_name}"))
        if self.p.has_savings and self.rng.random() < CASH_DEPOSIT_CHANCE:
            self._add(self._random_day(month_start),
                      Leg(self.savings, Direction.IN, self._amount(*CASH_DEPOSIT_RANGE), Channel.DEPOSIT,
                          "Cash deposit", "Cash deposit at branch"))


def generate_events(
    customers: tuple[CustomerProfile, ...], peers: tuple[CustomerProfile, ...], *,
    seed: str, months: int, today: date, tz: tzinfo, now: datetime,
) -> list[SeedEvent]:
    """All customers' events, oldest first. `peers` are who internal transfers go to."""
    start = add_months(today.replace(day=1), -months)
    events: list[SeedEvent] = []
    for profile in customers:
        others = tuple(p for p in peers if p.username != profile.username)
        history = _CustomerHistory(profile, others, seed, tz, now)
        history.opening(start - timedelta(days=1))  # before the first month's activity
        for offset in range(months, -1, -1):
            history.month(add_months(today.replace(day=1), -offset))
        events.extend(history.events)
    return sorted(events, key=lambda e: (e.when, e.rng_key))


def _reference(seed: str, key: str, prefix: str, used: set[str]) -> str:
    rng = random.Random(f"{seed}:ref:{key}")
    while True:
        reference = prefix + "".join(rng.choice(REFERENCE_CHARS) for _ in range(REFERENCE_RANDOM_LENGTH))
        if reference not in used:
            used.add(reference)
            return reference


def post_events(
    events: list[SeedEvent], opening_balances: dict[str, Decimal], *, seed: str, reference_prefix: str
) -> tuple[list[PostedLeg], dict[str, Decimal]]:
    """Apply events in order. Returns the posted legs and the final balance of every account."""
    balances = dict(opening_balances)
    posted: list[PostedLeg] = []
    used: set[str] = set()
    for event in events:
        outgoing = [leg for leg in event.legs if leg.direction is Direction.OUT]
        if any(balances[leg.account_number] < leg.amount for leg in outgoing):
            continue  # would overdraw: this customer "didn't make" that payment
        reference = _reference(seed, event.rng_key, reference_prefix, used)
        for leg in event.legs:
            sign = -1 if leg.direction is Direction.OUT else 1
            balances[leg.account_number] += sign * leg.amount
            posted.append(PostedLeg(leg, event.when, reference, balances[leg.account_number]))
    return posted, balances
