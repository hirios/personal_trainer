"""
Instâncias das extensões Flask.
Inicializadas aqui sem app para permitir o padrão Application Factory.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ORM principal — todas as models importam `db` daqui
db = SQLAlchemy()

# Gerenciamento de migrações via Alembic
migrate = Migrate()

# Autenticação JWT
jwt = JWTManager()

# Envio de e-mails
mail = Mail()

# Cross-Origin Resource Sharing
cors = CORS()

# Rate limiting por IP
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)

# Requisições OPTIONS (preflight CORS) são excluídas — não consomem cota
@limiter.request_filter
def _exempt_options():
    from flask import request
    return request.method == "OPTIONS"
