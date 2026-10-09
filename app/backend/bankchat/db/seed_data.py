"""Fictional seed data for the Benki Yetu simulation. DEV ONLY: no real people, numbers or customers.

The three test users can log in (password from SEED_DEV_PASSWORD, default "password123").
The other customers cannot log in; they exist so internal transfers have someone to go to.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CustomerProfile:
    index: int                    # makes the account numbers
    username: str
    full_name: str
    phone: str
    can_login: bool
    savings_opening: int          # KES at the start of the history
    current_opening: int
    employer: str | None = None
    monthly_salary: int = 0
    monthly_rent: int = 0
    savings_rate: float = 0.0     # share of salary moved to savings after payday
    has_savings: bool = True


TEST_CUSTOMERS: tuple[CustomerProfile, ...] = (
    CustomerProfile(
        index=1, username="amina", full_name="Amina Hassan", phone="254712000101", can_login=True,
        savings_opening=180_000, current_opening=45_000, employer="Savannah Logistics Ltd",
        monthly_salary=145_000, monthly_rent=38_000, savings_rate=0.15,
    ),
    CustomerProfile(
        index=2, username="brian", full_name="Brian Otieno", phone="254722000202", can_login=True,
        savings_opening=35_000, current_opening=18_000, employer="Kilimo Tech Ltd",
        monthly_salary=98_000, monthly_rent=22_000, savings_rate=0.08,
    ),
    CustomerProfile(
        index=3, username="wanjiku", full_name="Wanjiku Kamau", phone="254733000303", can_login=True,
        savings_opening=420_000, current_opening=90_000, employer="Mwangaza Hospital",
        monthly_salary=210_000, monthly_rent=55_000, savings_rate=0.20,
    ),
)

# Other Benki Yetu customers: receive internal transfers, cannot log in.
OTHER_CUSTOMERS: tuple[CustomerProfile, ...] = (
    CustomerProfile(index=11, username="grace", full_name="Grace Njeri", phone="254711000411",
                    can_login=False, savings_opening=0, current_opening=12_000, has_savings=False),
    CustomerProfile(index=12, username="kevin", full_name="Kevin Mutua", phone="254711000412",
                    can_login=False, savings_opening=0, current_opening=8_500, has_savings=False),
    CustomerProfile(index=13, username="fatuma", full_name="Fatuma Ali", phone="254711000413",
                    can_login=False, savings_opening=0, current_opening=25_000, has_savings=False),
)

# (name, till number, min KES, max KES)
TILLS: tuple[tuple[str, str, int, int], ...] = (
    ("Soko Fresh Supermarket", "512345", 450, 6_500),
    ("Kahawa House Cafe", "623451", 250, 1_800),
    ("Jirani Mart", "734512", 150, 2_500),
    ("Petro Point Fuel", "845123", 2_000, 7_000),
    ("Uhuru Pharmacy", "956234", 300, 3_500),
    ("Mama Mboga Greens", "567812", 100, 900),
)

# (name, paybill number, account at the biller, min KES, max KES)
UTILITY_PAYBILLS: tuple[tuple[str, str, str, int, int], ...] = (
    ("Power Utility Prepaid", "818181", "METER{index}0042", 1_500, 4_500),
    ("City Water Services", "727272", "WTR{index}0917", 800, 2_200),
    ("Mtandao Home Fibre", "636363", "FIB{index}5521", 2_999, 2_999),
)
RENT_PAYBILL = ("Makazi Property Managers", "545454", "UNIT{index}B")

# (name, phone) for M-Pesa sends and receipts.
MPESA_CONTACTS: tuple[tuple[str, str], ...] = (
    ("Mama Otieno", "254722111222"),
    ("John Kariuki", "254733222333"),
    ("Esther Wambui", "254711333444"),
    ("Hassan Omar", "254799444555"),
    ("Peter Mwangi", "254700555666"),
)

# (bank name as in bank.json, payee name, account number)
PESALINK_PAYEES: tuple[tuple[str, str, str], ...] = (
    ("equity", "Jane Mwende", "0170293845561"),
    ("kcb", "Daniel Kiprop", "1189203746"),
    ("ncba", "Lucy Achieng", "8827364510"),
    ("co-op", "Samuel Njoroge", "01109283746500"),
)

SAVINGS_PREFIX = "11"
CURRENT_PREFIX = "12"
ACCOUNT_SERIAL_DIGITS = 10


def savings_number(index: int) -> str:
    return f"{SAVINGS_PREFIX}{index:0{ACCOUNT_SERIAL_DIGITS}d}"


def current_number(index: int) -> str:
    return f"{CURRENT_PREFIX}{index:0{ACCOUNT_SERIAL_DIGITS}d}"
