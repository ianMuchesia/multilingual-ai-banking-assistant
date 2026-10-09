"""The money path: chat prepares, only confirm executes, and every safety check holds."""

from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bankchat.clock import utc_now
from bankchat.db.models import PendingAction, RouterAudit, Transaction
from bankchat.db.seed_data import current_number
from tests.conftest import login

BRIAN_INDEX = 2


def _accounts(client: TestClient, headers: dict[str, str]) -> dict[str, dict]:
    response = client.get("/api/accounts", headers=headers)
    assert response.status_code == 200
    return {a["type"]: a for a in response.json()}


def _tx_count(db: Session) -> int:
    return db.scalar(select(func.count(Transaction.id))) or 0


def _chat(client: TestClient, headers: dict[str, str], message: str) -> dict:
    response = client.post("/api/chat", json={"message": message}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _prepare(client: TestClient, headers: dict[str, str], message: str) -> dict:
    body = _chat(client, headers, message)
    assert body["decision"]["route"] == "confirm", body
    assert body["reply"]["kind"] == "confirm"
    assert body["pending_action"] is not None
    return body["pending_action"]


# --- auth -----------------------------------------------------------------------------------

def test_login_and_me(client: TestClient) -> None:
    headers = login(client, "amina")
    me = client.get("/api/me", headers=headers).json()
    assert me["username"] == "amina"
    assert {a["type"] for a in me["accounts"]} == {"savings", "current"}
    assert all(a["currency"] == "KES" for a in me["accounts"])


def test_bad_password_is_401(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "amina", "password": "wrong"})
    assert response.status_code == 401


def test_receive_only_customer_cannot_log_in(client: TestClient) -> None:
    response = client.post("/api/auth/login", json={"username": "grace", "password": "password123"})
    assert response.status_code == 401


def test_endpoints_require_a_token(client: TestClient) -> None:
    assert client.get("/api/accounts").status_code == 401
    assert client.post("/api/chat", json={"message": "balance"}).status_code == 401
    assert client.get("/api/accounts", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "router_mode": "stub"}


# --- chat never moves money -----------------------------------------------------------------

def test_chat_prepares_but_never_moves_money(client: TestClient, db: Session) -> None:
    headers = login(client, "amina")
    before, count_before = _accounts(client, headers), _tx_count(db)

    action = _prepare(client, headers, "transfer 5000 from current to savings")

    assert action["intent"] == "internal_transfer"
    assert action["missing_slots"] == []
    assert action["slots"]["amount"] == 5000
    assert action["slots"]["from_account"] == before["current"]["number"]
    assert action["slots"]["to_account"] == before["savings"]["number"]
    assert _accounts(client, headers) == before
    assert _tx_count(db) == count_before


def test_every_chat_message_is_audited(client: TestClient, db: Session) -> None:
    headers = login(client, "amina")
    _chat(client, headers, "what is my balance")
    _chat(client, headers, "asdf qwerty")
    rows = db.scalars(select(RouterAudit).order_by(RouterAudit.id)).all()
    assert [r.reply_kind for r in rows] == ["balance", "llm_pending"]
    assert all(r.router_mode == "stub" and r.reasons for r in rows)


def test_question_about_sending_creates_no_action(client: TestClient) -> None:
    body = _chat(client, login(client, "amina"), "can I send 5000 to 0712345678?")
    assert body["pending_action"] is None
    assert body["reply"]["kind"] == "llm_pending"


# --- confirm executes -------------------------------------------------------------------------

def test_confirm_internal_transfer_moves_both_sides(client: TestClient) -> None:
    headers = login(client, "amina")
    before = _accounts(client, headers)
    action = _prepare(client, headers, "transfer 5000 from current to savings")

    response = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "executed"
    tx = body["transaction"]
    assert (tx["direction"], tx["amount"], tx["channel"]) == ("out", 5000, "internal")
    assert body["receipt"]["reference"] == tx["reference"]
    assert body["receipt"]["from_account"] == before["current"]["number"]

    after = _accounts(client, headers)
    assert Decimal(str(after["current"]["balance"])) == Decimal(str(before["current"]["balance"])) - 5000
    assert Decimal(str(after["savings"]["balance"])) == Decimal(str(before["savings"]["balance"])) + 5000
    assert tx["balance_after"] == after["current"]["balance"]

    incoming = client.get(
        "/api/transactions", params={"account_id": after["savings"]["id"], "limit": 1}, headers=headers
    ).json()[0]
    assert (incoming["reference"], incoming["direction"], incoming["amount"]) == (tx["reference"], "in", 5000)

    receipt = client.get(f"/api/transactions/{tx['reference']}/receipt", headers=headers)
    assert receipt.status_code == 200
    assert receipt.json()["status"] == "completed"


def test_transfer_to_another_customer_credits_them(client: TestClient, db: Session) -> None:
    headers = login(client, "amina")
    brian_current = current_number(BRIAN_INDEX)
    brian_before = _accounts(client, login(client, "brian"))["current"]["balance"]
    action = _prepare(client, headers, f"send 1200 to {brian_current}")

    response = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers)

    assert response.status_code == 200, response.text
    brian_after = _accounts(client, login(client, "brian"))["current"]["balance"]
    assert Decimal(str(brian_after)) == Decimal(str(brian_before)) + 1200


def test_confirm_mpesa_transfer(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "send 1,500 to 0712345678")
    assert action["slots"]["destination"] == "254712345678"

    body = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers).json()

    assert body["transaction"]["channel"] == "mpesa"
    assert body["transaction"]["counterparty"] == "M-Pesa 254712345678"


def test_confirm_till_payment(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "pay till 512345 KES 750")

    body = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers).json()

    assert (body["transaction"]["channel"], body["transaction"]["amount"]) == ("till", 750)


# --- confirm refuses ---------------------------------------------------------------------------

def test_missing_slots_are_400_then_can_be_supplied(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "send money to my KCB account")
    assert set(action["missing_slots"]) == {"destination", "amount"}

    refused = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers)
    assert refused.status_code == 400
    assert "missing" in refused.json()["detail"]

    slots = {"destination": "1189203746", "amount": 2500}
    response = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": slots}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["transaction"]["channel"] == "pesalink"


def test_insufficient_funds_is_400_and_changes_nothing(client: TestClient, db: Session) -> None:
    headers = login(client, "amina")
    before, count_before = _accounts(client, headers), _tx_count(db)
    action = _prepare(client, headers, "send 1,500 to 0712345678")
    too_much = int(before["current"]["balance"]) + 100

    response = client.post(
        f"/api/actions/{action['id']}/confirm", json={"slots": {"amount": too_much}}, headers=headers
    )

    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"]
    assert _accounts(client, headers) == before
    assert _tx_count(db) == count_before
    # Still pending: the customer can retry with a smaller amount.
    retry = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {"amount": 100}}, headers=headers)
    assert retry.status_code == 200


def test_cannot_debit_someone_elses_account(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "send 1,500 to 0712345678")
    slots = {"from_account": current_number(BRIAN_INDEX)}

    response = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": slots}, headers=headers)

    assert response.status_code == 400


def test_unknown_slot_and_bad_amount_are_400(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "send 1,500 to 0712345678")
    url = f"/api/actions/{action['id']}/confirm"
    assert client.post(url, json={"slots": {"pin": "1234"}}, headers=headers).status_code == 400
    assert client.post(url, json={"slots": {"amount": -5}}, headers=headers).status_code == 400
    assert client.post(url, json={"slots": {"amount": "lots"}}, headers=headers).status_code == 400
    assert client.post(url, json={"slots": {"amount": 1.234}}, headers=headers).status_code == 400


def test_confirm_twice_is_409(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "pay till 512345 KES 750")
    url = f"/api/actions/{action['id']}/confirm"
    assert client.post(url, json={"slots": {}}, headers=headers).status_code == 200
    assert client.post(url, json={"slots": {}}, headers=headers).status_code == 409


def test_other_customer_gets_404(client: TestClient) -> None:
    action = _prepare(client, login(client, "amina"), "pay till 512345 KES 750")
    brian = login(client, "brian")
    assert client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=brian).status_code == 404
    assert client.post(f"/api/actions/{action['id']}/cancel", headers=brian).status_code == 404


def test_unknown_action_is_404(client: TestClient) -> None:
    headers = login(client, "amina")
    response = client.post("/api/actions/does-not-exist/confirm", json={"slots": {}}, headers=headers)
    assert response.status_code == 404


def test_expired_action_is_409(client: TestClient, db: Session) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "pay till 512345 KES 750")
    row = db.get(PendingAction, action["id"])
    row.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()

    response = client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers)

    assert response.status_code == 409
    db.expire_all()
    assert db.get(PendingAction, action["id"]).status == "expired"


def test_cancel_then_confirm_is_409(client: TestClient) -> None:
    headers = login(client, "amina")
    action = _prepare(client, headers, "pay till 512345 KES 750")

    cancelled = client.post(f"/api/actions/{action['id']}/cancel", headers=headers)

    assert cancelled.json() == {"status": "cancelled"}
    assert client.post(f"/api/actions/{action['id']}/confirm", json={"slots": {}}, headers=headers).status_code == 409


# --- read-only endpoints -------------------------------------------------------------------------

def test_transactions_are_scoped_to_the_customer(client: TestClient) -> None:
    amina = login(client, "amina")
    brian_accounts = _accounts(client, login(client, "brian"))
    response = client.get("/api/transactions", params={"account_id": brian_accounts["current"]["id"]}, headers=amina)
    assert response.status_code == 404
    rows = client.get("/api/transactions", params={"limit": 5}, headers=amina).json()
    assert len(rows) == 5


def test_view_replies(client: TestClient) -> None:
    headers = login(client, "amina")
    balance = _chat(client, headers, "what is my balance")
    assert balance["reply"]["kind"] == "balance"
    assert len(balance["reply"]["data"]["accounts"]) == 2
    statement = _chat(client, headers, "statement for the last 3 months")
    assert statement["reply"]["kind"] == "full_statement"
    assert statement["reply"]["data"]["transactions"]
    salary = _chat(client, headers, "did my salary come in")
    assert salary["reply"]["kind"] == "find_transaction"
    assert all(t["channel"] == "salary" for t in salary["reply"]["data"]["matches"])
    help_reply = _chat(client, headers, "what is the pesalink limit")
    assert help_reply["reply"]["data"]["topic"] == "pesalink"
