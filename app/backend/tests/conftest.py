"""Shared fixtures: an in-memory SQLite app with the stub router and the full seed."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from bankchat.app_factory import create_app
from bankchat.db.seed import seed_database
from bankchat.db.session import create_schema
from bankchat.settings import Settings
from bankchat.slots.bank_directory import BankDirectory, load_bank_directory

TEST_PASSWORD = "password123"
TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"
TEST_JWT_SECRET = "test-only-secret-0123456789"
FAST_BCRYPT_ROUNDS = 4


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        jwt_secret=TEST_JWT_SECRET,
        router_mode="stub",
        bcrypt_rounds=FAST_BCRYPT_ROUNDS,
        seed_dev_password=TEST_PASSWORD,
    )


@pytest.fixture(scope="session")
def bank(settings: Settings) -> BankDirectory:
    return load_bank_directory(settings.bank_config_path)


@pytest.fixture()
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app) as test_client:
        create_schema(app.state.engine)
        with app.state.session_factory() as session:
            seed_database(session, settings)
        yield test_client


@pytest.fixture()
def db(client: TestClient) -> Iterator[Session]:
    with client.app.state.session_factory() as session:  # type: ignore[attr-defined]
        yield session


def login(client: TestClient, username: str, password: str = TEST_PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    if response.status_code != 200:
        raise RuntimeError(f"login failed for {username}: {response.status_code} {response.text}")
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
