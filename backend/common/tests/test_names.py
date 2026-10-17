from types import SimpleNamespace

from common.names import display_name


def test_full_name_wins_over_login():
    assert display_name(SimpleNamespace(first_name="Анна", last_name="Ковалёва", username="demo_anna")) == "Анна Ковалёва"


def test_login_when_no_name():
    assert display_name(SimpleNamespace(first_name="", last_name="", username="demo_anna")) == "demo_anna"


def test_no_user():
    assert display_name(None) == ""
