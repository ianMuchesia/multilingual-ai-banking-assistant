"""The keyword stand-in router: same shape and the same safety policy as the real one."""

import pytest

from bankchat.router_client.stub import StubRouterClient
from bankchat.services.transfer_help import load_transfer_faq
from bankchat.settings import Settings
from bankchat.slots.bank_directory import BankDirectory


@pytest.fixture(scope="module")
def stub(bank: BankDirectory) -> StubRouterClient:
    return StubRouterClient(bank)


@pytest.mark.parametrize(
    ("text", "intent", "route"),
    [
        ("what is my balance", "balance_inquiry", "direct"),
        ("show my last 5 transactions", "mini_statement", "direct"),
        ("statement for the last 3 months", "full_statement", "direct"),
        ("did my salary come in", "find_transaction", "direct"),
        ("receipt for BY4K7Q2M9X", "view_receipt", "direct"),
        ("transfer 5000 from current to savings", "internal_transfer", "confirm"),
        ("send 1,500 to 0712345678", "external_transfer", "confirm"),
        ("send 2000 to equity account 0123456789", "external_transfer", "confirm"),
        ("pay till 512345 KES 750", "lipa_na_mpesa", "confirm"),
        ("what is the pesalink limit", "transfer_help", "direct"),
        ("I want a loan", "unsupported", "reject"),
        ("asdf qwerty", "unsupported", "llm"),
    ],
)
def test_stub_routes(stub: StubRouterClient, text: str, intent: str, route: str) -> None:
    decision = stub.route(text)
    assert (decision.intent, decision.route) == (intent, route)
    assert len(decision.top3) == 3
    assert decision.reasons


def test_action_phrased_as_question_goes_to_llm(stub: StubRouterClient) -> None:
    decision = stub.route("can I send 5000 to 0712345678?")
    assert decision.route == "llm"


def test_faq_topics(settings: Settings) -> None:
    faq = load_transfer_faq(settings.transfer_faq_path)
    assert faq.find("what is the pesalink limit").id == "pesalink"
    assert faq.find("how much does rtgs cost").id == "rtgs"
    assert faq.find("tell me about transfers").id == "overview"
    assert "DEMO" in faq.disclaimer
