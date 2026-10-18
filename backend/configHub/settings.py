from pathlib import Path
import os

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.getenv("FILEHUB_CONFIG_PATH", "/etc/filehub/config.yaml"))
if CONFIG_PATH.exists():
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        DEPLOY_CONFIG = yaml.safe_load(config_file)
    if DEPLOY_CONFIG is None:
        DEPLOY_CONFIG = {}
    if not isinstance(DEPLOY_CONFIG, dict):
        raise ValueError(f"FileHub config must contain a YAML mapping: {CONFIG_PATH}")
else:
    DEPLOY_CONFIG = {}


def config_value(key, environment_key, default):
    return DEPLOY_CONFIG.get(key, os.getenv(environment_key, default))


def config_list(key, environment_key, default):
    value = config_value(key, environment_key, default)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [item.strip() for item in value if item.strip()]
    raise ValueError(f"{key} must be a string or list of strings")


def config_section(name):
    section = DEPLOY_CONFIG.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"{name} must be a YAML mapping")
    return section


def config_bool(section, key, default):
    value = section.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        return value.lower() in {"true", "1", "yes", "on"}
    raise ValueError(f"{key} must be a boolean")


def config_nonnegative_int(section, key, default):
    value = section.get(key, default)
    if type(value) is not int or value < 0:
        raise ValueError(f"{key} must be a non-negative integer")
    return value


SECRET_KEY = config_value("secret_key", "DJANGO_SECRET_KEY", "dev-only-confighub-secret-key")
DEBUG = str(config_value("debug", "DJANGO_DEBUG", "1")).lower() in {"1", "true", "yes", "on"}
ALLOWED_HOSTS = config_list("allowed_hosts", "DJANGO_ALLOWED_HOSTS", "*")
APPLICATION_CONFIG = config_section("application")
SECURITY_CONFIG = config_section("security")
DATABASE_CONFIG = config_section("database")
CHANNEL_CONFIG = config_section("channels")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "configHub.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "configHub.wsgi.application"
ASGI_APPLICATION = "configHub.asgi.application"
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}
channel_backend = str(CHANNEL_CONFIG.get("backend", "memory")).lower()
if channel_backend == "redis":
    redis_config = CHANNEL_CONFIG.get("redis", {})
    if not isinstance(redis_config, dict):
        raise ValueError("channels.redis must be a YAML mapping")
    redis_url = redis_config.get("url", "redis://127.0.0.1:6379/0")
    if not isinstance(redis_url, str) or not redis_url.startswith(("redis://", "rediss://")):
        raise ValueError("channels.redis.url must use redis:// or rediss://")
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [redis_url]},
        },
    }
elif channel_backend not in {"memory", "inmemory"}:
    raise ValueError("channels.backend must be memory or redis")

database_engine = str(DATABASE_CONFIG.get("engine", "sqlite")).lower()
if database_engine == "sqlite":
    sqlite_options = DATABASE_CONFIG.get("options", {})
    if not isinstance(sqlite_options, dict):
        raise ValueError("database.options must be a YAML mapping")
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_CONFIG.get("name", DEPLOY_CONFIG.get("database_path", os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")))),
        "OPTIONS": sqlite_options,
    }}
elif database_engine in {"mysql", "mariadb"}:
    import pymysql

    pymysql.install_as_MySQLdb()
    mysql_options = DATABASE_CONFIG.get("options", {"charset": "utf8mb4"})
    if not isinstance(mysql_options, dict):
        raise ValueError("database.options must be a YAML mapping")
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DATABASE_CONFIG.get("name", "filehub"),
        "USER": DATABASE_CONFIG.get("user", "filehub"),
        "PASSWORD": DATABASE_CONFIG.get("password", ""),
        "HOST": DATABASE_CONFIG.get("host", "127.0.0.1"),
        "PORT": str(DATABASE_CONFIG.get("port", 3306)),
        "CONN_MAX_AGE": DATABASE_CONFIG.get("conn_max_age", 60),
        "CONN_HEALTH_CHECKS": DATABASE_CONFIG.get("conn_health_checks", True),
        "OPTIONS": mysql_options,
    }}
else:
    raise ValueError("database.engine must be sqlite or mysql")

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = APPLICATION_CONFIG.get("language_code", "zh-hans")
TIME_ZONE = APPLICATION_CONFIG.get("time_zone", "Asia/Shanghai")
USE_I18N = config_bool(APPLICATION_CONFIG, "use_i18n", True)
USE_TZ = config_bool(APPLICATION_CONFIG, "use_tz", True)
STATIC_URL = APPLICATION_CONFIG.get("static_url", "static/")
STATIC_ROOT = APPLICATION_CONFIG.get("static_root", str(BASE_DIR / "staticfiles"))
DATA_UPLOAD_MAX_MEMORY_SIZE = APPLICATION_CONFIG.get("data_upload_max_memory_size", 2_621_440)
FILE_UPLOAD_MAX_MEMORY_SIZE = APPLICATION_CONFIG.get("file_upload_max_memory_size", 2_621_440)
FILE_UPLOAD_TEMP_DIR = APPLICATION_CONFIG.get("file_upload_temp_dir")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ALLOWED_ORIGINS = config_list("cors_allowed_origins", "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
CSRF_TRUSTED_ORIGINS = config_list("csrf_trusted_origins", "CSRF_TRUSTED_ORIGINS", "")
if config_bool(SECURITY_CONFIG, "trust_proxy_ssl_header", True):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = config_bool(SECURITY_CONFIG, "secure_ssl_redirect", False)
SESSION_COOKIE_SECURE = config_bool(SECURITY_CONFIG, "session_cookie_secure", False)
CSRF_COOKIE_SECURE = config_bool(SECURITY_CONFIG, "csrf_cookie_secure", False)
SESSION_COOKIE_HTTPONLY = config_bool(SECURITY_CONFIG, "session_cookie_httponly", True)
CSRF_COOKIE_HTTPONLY = config_bool(SECURITY_CONFIG, "csrf_cookie_httponly", False)
SECURE_HSTS_SECONDS = config_nonnegative_int(SECURITY_CONFIG, "hsts_seconds", 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config_bool(SECURITY_CONFIG, "hsts_include_subdomains", False)
SECURE_HSTS_PRELOAD = config_bool(SECURITY_CONFIG, "hsts_preload", False)
SECURE_CONTENT_TYPE_NOSNIFF = config_bool(SECURITY_CONFIG, "content_type_nosniff", True)
SECURE_REFERRER_POLICY = SECURITY_CONFIG.get("referrer_policy", "same-origin")
USE_X_FORWARDED_HOST = config_bool(SECURITY_CONFIG, "use_x_forwarded_host", False)
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "dashboard.authentication.ExpiryTokenAuthentication",
    ],
}
