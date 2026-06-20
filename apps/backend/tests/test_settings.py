"""Settings behavior: env-prefix isolation, secure defaults, secret masking."""

from pathlib import Path

import pytest

from restart_api.settings import Settings


class TestDefaults:
    def test_secure_defaults(self) -> None:
        s = Settings(_env_file=None)
        assert s.app_env == "dev"
        assert s.debug is False
        # No credentialed defaults exist anywhere in code.
        assert s.database_url is None
        assert s.redis_url is None
        assert s.api_key is None

    def test_dev_cors_default_is_localhost_only(self) -> None:
        s = Settings(_env_file=None)
        assert s.cors_origins == ["http://localhost:3000"]

    def test_studies_dir_defaults_to_optimization_studies(self) -> None:
        # Read-only optimization surface loads study.json from here as DATA.
        assert Settings(_env_file=None).studies_dir == Path("optimization_studies")


class TestEnvBinding:
    def test_prefixed_env_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RESTART_APP_ENV", "prod")
        monkeypatch.setenv("RESTART_DEBUG", "true")
        monkeypatch.setenv("RESTART_CORS_ORIGINS", '["https://restart-lab.example"]')
        s = Settings(_env_file=None)
        assert s.app_env == "prod"
        assert s.debug is True
        assert s.cors_origins == ["https://restart-lab.example"]

    def test_unprefixed_env_is_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("APP_ENV", "prod")
        assert Settings(_env_file=None).app_env == "dev"

    def test_invalid_app_env_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RESTART_APP_ENV", "staging")
        with pytest.raises(ValueError, match="app_env"):
            Settings(_env_file=None)


class TestSecretHandling:
    def test_secrets_masked_in_repr_and_str(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RESTART_API_KEY", "super-secret-key")
        monkeypatch.setenv("RESTART_DATABASE_URL", "postgresql://u:pw@h/db")
        s = Settings(_env_file=None)
        for rendering in (repr(s), str(s)):
            assert "super-secret-key" not in rendering
            assert "pw" not in rendering
        assert s.api_key is not None
        assert s.api_key.get_secret_value() == "super-secret-key"
