from mielelogic_api.settings import load_environment_credentials


def test_load_environment_credentials(monkeypatch):
    monkeypatch.setenv("mielelogic_username", "user@example.com")
    monkeypatch.setenv("mielelogic_password", "secret")
    monkeypatch.setenv("mielelogic_scope", "DA")

    credentials = load_environment_credentials()

    assert credentials is not None
    assert credentials.username.get_secret_value() == "user@example.com"
    assert credentials.password.get_secret_value() == "secret"
    assert credentials.scope == "DA"
