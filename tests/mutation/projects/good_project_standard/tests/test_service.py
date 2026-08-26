"""Tests for the service layer."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from service import Service, UserRepository


def test_get_user():
    svc = Service(UserRepository())
    user = svc.get_user(1)
    assert user["id"] == 1


def test_create_user():
    svc = Service(UserRepository())
    user = svc.create_user("alice")
    assert user["name"] == "alice"