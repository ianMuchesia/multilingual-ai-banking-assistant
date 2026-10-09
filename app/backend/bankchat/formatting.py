"""Human-readable money and account formatting for chat replies."""

from decimal import Decimal


def format_money(amount: Decimal | float, currency: str) -> str:
    return f"{currency} {Decimal(str(amount)):,.2f}"


def mask_account(number: str) -> str:
    """Show only the last 4 digits: ****0001."""
    return f"****{number[-4:]}"
