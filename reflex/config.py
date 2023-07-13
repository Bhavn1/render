"""The Reflex config."""

from __future__ import annotations

import importlib
import os
import sys
import urllib.parse
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from reflex import constants
from reflex.admin import AdminDash
from reflex.base import Base


class DBConfig(Base):
    """Database config."""

    engine: str
    username: Optional[str] = ""
    password: Optional[str] = ""
    host: Optional[str] = ""
    port: Optional[int] = None
    database: str

    @classmethod
    def postgresql(
        cls,
        database: str,
        username: str,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = 5432,
    ) -> DBConfig:
        """Create an instance with postgresql engine.

        Args:
            database: Database name.
            username: Database username.
            password: Database password.
            host: Database host.
            port: Database port.

        Returns:
            DBConfig instance.
        """
        return cls(
            engine="postgresql",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

    @classmethod
    def postgresql_psycopg2(
        cls,
        database: str,
        username: str,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = 5432,
    ) -> DBConfig:
        """Create an instance with postgresql+psycopg2 engine.

        Args:
            database: Database name.
            username: Database username.
            password: Database password.
            host: Database host.
            port: Database port.

        Returns:
            DBConfig instance.
        """
        return cls(
            engine="postgresql+psycopg2",
            username=username,
            password=password,
            host=host,
            port=port,
            database=database,
        )

    @classmethod
    def sqlite(
        cls,
        database: str,
    ) -> DBConfig:
        """Create an instance with sqlite engine.

        Args:
            database: Database name.

        Returns:
            DBConfig instance.
        """
        return cls(
            engine="sqlite",
            database=database,
        )

    def get_url(self) -> str:
        """Get database URL.

        Returns:
            The database URL.
        """
        host = (
            f"{self.host}:{self.port}" if self.host and self.port else self.host or ""
        )
        username = urllib.parse.quote_plus(self.username) if self.username else ""
        password = urllib.parse.quote_plus(self.password) if self.password else ""

        if username:
            path = f"{username}:{password}@{host}" if password else f"{username}@{host}"
        else:
            path = f"{host}"

        return f"{self.engine}://{path}/{self.database}"


class Config(Base):
    """A Reflex config."""

    # The name of the app.
    app_name: str

    # The username.
    username: Optional[str] = None

    # The frontend port.
    frontend_port: str = constants.FRONTEND_PORT

    # The backend port.
    backend_port: str = constants.BACKEND_PORT

    # The backend host.
    backend_host: str = constants.BACKEND_HOST

    # The backend API url.
    api_url: str = constants.API_URL

    # The deploy url.
    deploy_url: Optional[str] = constants.DEPLOY_URL

    # The database url.
    db_url: Optional[str] = constants.DB_URL

    # The database config.
    db_config: Optional[DBConfig] = None

    # The redis url.
    redis_url: Optional[str] = constants.REDIS_URL

    # Telemetry opt-in.
    telemetry_enabled: bool = True

    # The rxdeploy url.
    rxdeploy_url: Optional[str] = None

    # The environment mode.
    env: constants.Env = constants.Env.DEV

    # The path to the bun executable.
    bun_path: str = constants.BUN_PATH

    # Disable bun.
    disable_bun: bool = False

    # Additional frontend packages to install.
    frontend_packages: List[str] = []

    # The Admin Dash.
    admin_dash: Optional[AdminDash] = None

    # Backend transport methods.
    backend_transports: Optional[
        constants.Transports
    ] = constants.Transports.WEBSOCKET_POLLING

    # List of origins that are allowed to connect to the backend API.
    cors_allowed_origins: Optional[list] = constants.CORS_ALLOWED_ORIGINS

    # Whether credentials (cookies, authentication) are allowed in requests to the backend API.
    cors_credentials: Optional[bool] = True

    # The maximum size of a message when using the polling backend transport.
    polling_max_http_buffer_size: Optional[int] = constants.POLLING_MAX_HTTP_BUFFER_SIZE

    # Dotenv file path.
    env_path: Optional[str] = constants.DOT_ENV_FILE

    # Whether to override OS environment variables.
    override_os_envs: Optional[bool] = True

    # Tailwind config.
    tailwind: Optional[Dict[str, Any]] = None

    # Timeout when launching the gunicorn server.
    timeout: int = constants.TIMEOUT

    # These fields are neither saved nor read from the environment
    _no_environment_fields = {
        "admin_dash",
        "db_config",
        "env",
        "frontend_packages",
        "override_os_envs",
        "tailwind",
    }

    # These fields are never derived from constants (environment only)
    _no_constants_fields = {"db_url"}

    def __init__(self, *args, **kwargs):
        """Initialize the config values.

        If db_url is not provided gets it from db_config.

        Args:
            *args: The args to pass to the Pydantic init method.
            **kwargs: The kwargs to pass to the Pydantic init method.
        """
        if "db_url" not in kwargs and "db_config" in kwargs:
            kwargs["db_url"] = kwargs["db_config"].get_url()

        super().__init__(*args, **kwargs)

        # set overriden class attribute values as os env variables to update constants
        constants_keys = dir(constants)
        for key, value in dict(self).items():
            key = key.upper()
            if (
                key.startswith("_")
                or key in os.environ
                or key not in constants_keys
                or (value is None and key != "DB_URL")
            ):
                continue
            os.environ[key] = str(value)

        # Avoid overriding if env_path is not provided or does not exist
        if self.env_path is not None and os.path.isfile(self.env_path):
            load_dotenv(self.env_path, override=self.override_os_envs)  # type: ignore
        # Recompute constants after loading env variables
        importlib.reload(constants)
        # Recompute instance attributes
        self.recompute_field_values()

    def _update_field_from_constants(self, field: str) -> Optional[bool]:
        """Derive the given field value from reflex.constants.

        Args:
            field: the config attribute to derive

        Returns:
            True if the field was updated
        """
        if field in self._no_constants_fields:
            return
        try:
            new_value = getattr(constants, f"{field.upper()}")
            if getattr(self, field) == new_value:
                return
            setattr(self, field, new_value)
            return True
        except AttributeError:
            pass

    def _update_field_from_environment(self, field: str) -> Optional[bool]:
        """Derive the given field value from environment variables.

        Args:
            field: the config attribute to derive

        Returns:
            True if the field was updated
        """
        if field in self._no_environment_fields:
            return
        env_value = constants.get_value(
            field.upper(),
            default=None,
            type_=self.__fields__[field].type_,
        )
        if env_value is not None:
            super().__setattr__(field, env_value)
            return True

    def recompute_field_values(self):
        """Recompute instance field values to reflect new values after reloading
        constant values.
        """
        for field in self.get_fields():
            if field.startswith("_"):
                continue
            if self._update_field_from_constants(field):
                continue
            self._update_field_from_environment(field)

    def __setattr__(self, key, value):
        """Save override values to the environment to avoid losing them."""
        super().__setattr__(key, value)
        if (
            key.startswith("_")
            or key in self._no_environment_fields
            or (value is None and key != "db_url")
        ):
            return  # not all variables are saved in the environment
        os.environ[key.upper()] = str(value)


def get_config() -> Config:
    """Get the app config.

    Returns:
        The app config.
    """
    from reflex.config import Config

    sys.path.append(os.getcwd())
    try:
        return __import__(constants.CONFIG_MODULE).config

    except ImportError:
        return Config(app_name="")  # type: ignore
