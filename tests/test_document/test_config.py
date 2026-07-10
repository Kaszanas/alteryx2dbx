from alteryx2dbx.document.config import load_config


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / ".alteryx2dbx.yml"
    config_file.write_text(
        "confluence:\n"
        "  url: https://company.atlassian.net\n"
        "  space: DATA-MIGRATION\n"
        '  parent_page: "Migration Reports"\n'
        "  pat: my-secret-token\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path)
    assert config is not None
    assert config["confluence"]["url"] == "https://company.atlassian.net"
    assert config["confluence"]["space"] == "DATA-MIGRATION"
    assert config["confluence"]["pat"] == "my-secret-token"


def test_load_config_no_file(tmp_path):
    config = load_config(tmp_path)
    assert config is None


def test_load_config_pat_from_env(tmp_path, monkeypatch):
    config_file = tmp_path / ".alteryx2dbx.yml"
    config_file.write_text(
        "confluence:\n"
        "  url: https://company.atlassian.net\n"
        "  space: DATA-MIGRATION\n"
        '  parent_page: "Migration Reports"\n'
        "  pat: ''\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CONFLUENCE_PAT", "env-token-123")
    config = load_config(tmp_path)
    assert config["confluence"]["pat"] == "env-token-123"


def test_load_config_walks_up_directories(tmp_path):
    config_file = tmp_path / ".alteryx2dbx.yml"
    config_file.write_text(
        "confluence:\n"
        "  url: https://example.com\n"
        "  space: TEST\n",
        encoding="utf-8",
    )
    subdir = tmp_path / "deep" / "nested"
    subdir.mkdir(parents=True)
    config = load_config(subdir)
    assert config is not None
    assert config["confluence"]["url"] == "https://example.com"


def test_load_config_explicit_path(tmp_path):
    config_file = tmp_path / "custom_config.yml"
    config_file.write_text(
        "confluence:\n"
        "  url: https://custom.com\n"
        "  space: CUSTOM\n",
        encoding="utf-8",
    )
    config = load_config(tmp_path, config_path=config_file)
    assert config["confluence"]["url"] == "https://custom.com"
