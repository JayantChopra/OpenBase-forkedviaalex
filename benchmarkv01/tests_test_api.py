"""
Simple API tests for the FastAPI app in api_fastapi.py. These tests avoid
external network calls and focus on basic validation behavior.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from benchmarkv01.api_fastapi import app


@pytest.fixture
def client():
    """Test client fixture for the FastAPI app."""
    return TestClient(app)


def test_health(client):
    """Health endpoint should return status ok and HTTP 200."""
    r = client.get("/health")
    if r.status_code != 200:
        pytest.fail(f"Expected status_code 200, got {r.status_code}")
    status = r.json().get("status") if isinstance(r.json(), dict) else None
    if status != "ok":
        pytest.fail(f"Expected status 'ok', got {status}")


def test_create_item_validation(client):
    """Creating items should validate required fields and return created item."""
    # Missing name should fail on the validated route
    r = client.post("/items", json={"quantity": 3})
    if r.status_code != 422:
        pytest.fail(f"Expected status_code 422 for missing name, got {r.status_code}")

    r = client.post("/items", json={"name": "widget", "quantity": 2})
    if r.status_code != 201:
        pytest.fail(f"Expected status_code 201 for valid item, got {r.status_code}")
    body = r.json()
    if body.get("name") != "widget":
        pytest.fail(f"Expected name 'widget', got {body.get('name')}")
    if body.get("quantity") != 2:
        pytest.fail(f"Expected quantity 2, got {body.get('quantity')}")


def test_unsafe_items(client):
    """Unsafe items endpoint should accept minimal input and reject empty bodies."""
    r = client.post("/unsafe-items", json={"name": "x"})
    if r.status_code != 200:
        pytest.fail(f"Expected status_code 200 for valid unsafe item, got {r.status_code}")

    r2 = client.post("/unsafe-items", json={})
    if r2.status_code != 400:
        pytest.fail(f"Expected status_code 400 for empty unsafe item, got {r2.status_code}")


def test_search_mixed_validation(client):
    """Search endpoint should parse valid limits and handle invalid casts."""
    r = client.get("/search", params={"q": "foo", "limit": "5"})
    if r.status_code != 200:
        pytest.fail(f"Expected status_code 200 for valid search, got {r.status_code}")
    if r.json().get("limit") != 5:
        pytest.fail(f"Expected limit 5 in response, got {r.json().get('limit')}")

    # Bad limit shows unsafe cast behavior
    r2 = client.get("/search", params={"limit": "not-an-int"})
    if r2.status_code not in (500, 422):
        pytest.fail(f"Expected status_code 500 or 422 for bad limit, got {r2.status_code}")