import pytest


def test_login_redirects_to_discord(client):
    response = client.get("/login", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "discord.com" in response.headers["location"]


def test_logout_clears_session(auth_client):
    response = auth_client.get("/logout", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/"


@pytest.mark.skip(reason="Task 7 (/groups route) not yet implemented")
def test_protected_route_redirects_when_not_logged_in(client):
    response = client.get("/groups", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]
