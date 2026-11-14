"""Shared MySQL SQLAlchemy engine builder with optional TLS/SSL support."""

import os
from urllib.parse import quote_plus
import certifi
from dotenv import load_dotenv
from sqlalchemy import create_engine


def _is_truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def build_ssl_connect_args(
    use_ssl: bool | str | None = None,
    ssl_ca: str | None = None,
    connect_timeout: int | None = None,
) -> dict:
    """Build PyMySQL connect_args for local non-SSL or cloud TLS connections."""
    connect_args: dict = {}
    if connect_timeout is not None:
        connect_args["connect_timeout"] = connect_timeout

    ca_path = (ssl_ca or "").strip()
    ssl_enabled = _is_truthy(use_ssl)

    if ca_path:
        if not os.path.exists(ca_path):
            raise FileNotFoundError(f"DB_SSL_CA certificate file not found: {ca_path}")
        connect_args["ssl_ca"] = ca_path
        connect_args["ssl_verify_cert"] = True
        connect_args["ssl_verify_identity"] = True
    elif ssl_enabled:
        connect_args["ssl_ca"] = certifi.where()
        connect_args["ssl_verify_cert"] = True
        connect_args["ssl_verify_identity"] = True

    return connect_args


def create_mysql_engine(
    user: str | None = None,
    password: str | None = None,
    host: str | None = None,
    port: str | int | None = None,
    db_name: str | None = None,
    use_ssl: bool | str | None = None,
    ssl_ca: str | None = None,
    connect_timeout: int | None = None,
    pool_recycle: int | None = None,
    pool_pre_ping: bool = True,
):
    """Create a SQLAlchemy MySQL engine from explicit values or environment variables."""
    load_dotenv()

    resolved_user = user if user is not None else os.getenv("DB_USER", "root")
    resolved_pass = quote_plus(
        (password if password is not None else os.getenv("DB_PASS", "")) or ""
    )
    resolved_host = host if host is not None else os.getenv("DB_HOST", "localhost")
    resolved_port = str(port if port is not None else os.getenv("DB_PORT", "3306"))
    resolved_db = db_name if db_name is not None else os.getenv("DB_NAME", "retail_dw")
    resolved_ca = ssl_ca if ssl_ca is not None else os.getenv("DB_SSL_CA", "")

    raw_ssl = use_ssl if use_ssl is not None else os.getenv("DB_SSL")
    if raw_ssl is None and resolved_host.endswith(".tidbcloud.com"):
        resolved_ssl: bool | str = True
    else:
        resolved_ssl = raw_ssl if raw_ssl is not None else "false"

    connection_url = (
        f"mysql+pymysql://{resolved_user}:{resolved_pass}"
        f"@{resolved_host}:{resolved_port}/{resolved_db}"
    )
    connect_args = build_ssl_connect_args(
        use_ssl=resolved_ssl,
        ssl_ca=resolved_ca,
        connect_timeout=connect_timeout,
    )

    engine_kwargs: dict = {"pool_pre_ping": pool_pre_ping}
    if connect_args:
        engine_kwargs["connect_args"] = connect_args
    if pool_recycle is not None:
        engine_kwargs["pool_recycle"] = pool_recycle

    return create_engine(connection_url, **engine_kwargs)
