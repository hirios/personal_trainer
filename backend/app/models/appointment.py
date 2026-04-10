"""
Model Appointment — agendamentos entre trainer e aluno.
Registra horário, local, status e histórico de cancelamentos.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Appointment(db.Model):
    """
    Representa uma sessão agendada entre personal trainer e aluno.

    Ciclo de vida de status:
      scheduled → confirmed → completed
      scheduled → cancelled_trainer / cancelled_student / no_show
      confirmed → completed / cancelled_trainer / no_show
    """

    __tablename__ = "appointments"

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
        db.ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Null = slot bloqueado pelo trainer (sem aluno vinculado)",
    )

    # --- Horário ---
    starts_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Início da sessão (UTC)",
    )
    ends_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        comment="Fim da sessão (UTC)",
    )

    # --- Status ---
    status = db.Column(
        db.String(30),
        nullable=False,
        default="scheduled",
        index=True,
        comment="scheduled | confirmed | completed | cancelled_trainer | cancelled_student | no_show",
    )

    # --- Detalhes ---
    location = db.Column(
        db.String(200),
        nullable=True,
        comment="Local da sessão (academia, endereço, online, etc.)",
    )
    notes = db.Column(
        db.Text,
        nullable=True,
        comment="Observações do agendamento visíveis ao aluno",
    )

    # --- Cancelamento ---
    cancellation_reason = db.Column(
        db.Text,
        nullable=True,
        comment="Motivo informado no cancelamento",
    )
    cancelled_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp do cancelamento",
    )

    # --- Auditoria ---
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

    # --- Relacionamentos ORM ---
    trainer = db.relationship("Trainer", back_populates="appointments", lazy="select")
    student = db.relationship("Student", back_populates="appointments", lazy="select")

    # --- Serialização ---
    def to_dict(self, include_student: bool = True, include_trainer: bool = False) -> dict:
        """Retorna dicionário serializável do agendamento."""
        data = {
            "id": self.id,
            "trainer_id": self.trainer_id,
            "student_id": self.student_id,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "status": self.status,
            "location": self.location,
            "notes": self.notes,
            "cancellation_reason": self.cancellation_reason,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_student and self.student:
            data["student"] = {
                "id": self.student.id,
                "name": self.student.name,
                "avatar_url": self.student.avatar_url,
                "phone": self.student.phone,
            }
        else:
            data["student"] = None

        if include_trainer and self.trainer:
            data["trainer"] = {
                "id": self.trainer.id,
                "name": self.trainer.name,
                "avatar_url": self.trainer.avatar_url,
            }

        return data

    def __repr__(self) -> str:
        return f"<Appointment {self.id[:8]} trainer={self.trainer_id[:8]} status={self.status}>"
