"""
Model base User com polimorfismo joined-table inheritance.
Trainer e Student herdam desta tabela compartilhando o mesmo id/email/password.
"""
import uuid
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db


def _uuid_str() -> str:
    """Gera um UUID v4 como string para usar como PK."""
    return str(uuid.uuid4())


class User(db.Model):
    """
    Tabela base para todos os usuários do sistema.
    Usa joined-table inheritance: cada subclasse tem sua própria tabela
    com FK para esta, permitindo queries polimórficas via SQLAlchemy.
    """

    __tablename__ = "users"

    # Configuração do polimorfismo
    __mapper_args__ = {
        "polymorphic_identity": "user",
        "polymorphic_on": "role",
    }

    # --- Campos ---
    id = db.Column(
        db.String(36),
        primary_key=True,
        default=_uuid_str,
        comment="UUID v4 gerado automaticamente",
    )
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.String(20),
        nullable=False,
        comment="trainer | student — controla o polimorfismo",
    )
    phone = db.Column(db.String(20), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Métodos de senha ---
    def set_password(self, password: str) -> None:
        """Gera hash bcrypt e armazena. Nunca salva a senha em texto plano."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verifica a senha contra o hash armazenado."""
        return check_password_hash(self.password_hash, password)

    # --- Serialização ---
    def to_dict(self) -> dict:
        """Retorna representação segura do usuário (sem password_hash)."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "phone": self.phone,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<User {self.role} {self.email}>"
