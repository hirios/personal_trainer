"""
Model Message — mensagens internas entre trainer e aluno.
Histórico completo de conversas por par trainer↔aluno.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Message(db.Model):
    """
    Representa uma mensagem da conversa interna entre um trainer e um aluno.

    sender_role define quem enviou:
      'trainer' → mensagem do personal para o aluno
      'student' → mensagem do aluno para o personal

    is_read é controlado pelo destinatário:
      - Quando sender_role='student', is_read é marcado pelo trainer ao abrir a conversa.
      - Quando sender_role='trainer', is_read seria marcado pelo aluno (futuro).
    """

    __tablename__ = "messages"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=_uuid_str,
        comment="UUID v4 gerado automaticamente",
    )

    # --- Relacionamentos ---
    trainer_id = db.Column(
        db.String(36),
        db.ForeignKey("trainers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id = db.Column(
        db.String(36),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Conteúdo ---
    sender_role = db.Column(
        db.String(10),
        nullable=False,
        comment="trainer | student",
    )
    content = db.Column(
        db.Text,
        nullable=False,
        comment="Conteúdo da mensagem (texto puro)",
    )

    # --- Leitura ---
    is_read = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="False = destinatário ainda não leu",
    )

    # --- Auditoria ---
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    # --- Relacionamentos ORM ---
    trainer = db.relationship("Trainer", foreign_keys=[trainer_id], lazy="select")
    student = db.relationship("Student", foreign_keys=[student_id], lazy="select")

    # --- Serialização ---
    def to_dict(self) -> dict:
        """Retorna dicionário serializável da mensagem."""
        return {
            "id": self.id,
            "trainer_id": self.trainer_id,
            "student_id": self.student_id,
            "sender_role": self.sender_role,
            "content": self.content,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"<Message {self.id[:8]} from={self.sender_role} read={self.is_read}>"
