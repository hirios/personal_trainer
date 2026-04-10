"""
Configurações da aplicação FitFlow Pro.
Cada classe representa um ambiente distinto.
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Configuração base compartilhada por todos os ambientes."""

    # Chave secreta da aplicação
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-insecure")

    # Banco de dados — apenas DATABASE_URL precisa mudar para trocar de SQLite para PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///fitflow.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,  # verifica conexões stale no pool
    }

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt-secret-key-insecure")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    # CORS
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.environ.get(
            "CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500"
        ).split(",")
        if origin.strip()
    ]

    # Flask-Limiter — usa memória se RATELIMIT_STORAGE_URL não estiver definido
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")
    RATELIMIT_DEFAULT = "200 per day;50 per hour"
    RATELIMIT_HEADERS_ENABLED = True

    # E-mail
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER", "FitFlow Pro <noreply@fitflowpro.com.br>"
    )

    # Integrações externas
    ASAAS_API_KEY = os.environ.get("ASAAS_API_KEY", "")
    ASAAS_ENVIRONMENT = os.environ.get("ASAAS_ENVIRONMENT", "sandbox")
    ASAAS_BASE_URL = (
        "https://sandbox.asaas.com/api/v3"
        if ASAAS_ENVIRONMENT == "sandbox"
        else "https://api.asaas.com/v3"
    )

    ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID", "")
    ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN", "")
    ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN", "")

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

    # URL base do frontend — usada para montar links de acesso do aluno
    # Em dev aponta para o Live Server; em produção aponta para o domínio real
    FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://127.0.0.1:6555")


class DevelopmentConfig(BaseConfig):
    """Configuração para desenvolvimento local."""

    DEBUG = True
    TESTING = False
    RATELIMIT_ENABLED = True

    # Em desenvolvimento aceita qualquer origem — evita problemas de CORS com Live Server,
    # Vite, extensões do VS Code, etc. Em produção use a lista explícita em CORS_ORIGINS.
    CORS_ORIGINS = "*"


class ProductionConfig(BaseConfig):
    """Configuração para produção."""

    DEBUG = False
    TESTING = False
    # Em produção, SESSION_COOKIE_SECURE exige HTTPS
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


class TestingConfig(BaseConfig):
    """Configuração para testes automatizados."""

    TESTING = True
    DEBUG = True
    # Banco em memória para testes rápidos e isolados
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    # Desativa rate limit para não interferir nos testes
    RATELIMIT_ENABLED = False
    # Tokens com validade curta para testar expiração
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(hours=1)
    WTF_CSRF_ENABLED = False


# Mapa de configurações — usado em create_app()
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
