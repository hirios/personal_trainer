"""
Model Trainer — herda de User via joined-table inheritance.
Armazena dados específicos do personal trainer.
"""
from datetime import datetime, timezone
from app.extensions import db
from .user import User


class Trainer(User):
    """
    Tabela complementar para personal trainers.
    Compartilha o id com a tabela users (FK + PK).
    """

    __tablename__ = "trainers"

    __mapper_args__ = {
        "polymorphic_identity": "trainer",
    }

    # FK para a tabela base
    id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)

    # --- Dados profissionais ---
    cref = db.Column(
        db.String(20),
        nullable=True,
        comment="Número de registro no CREF (opcional no cadastro)",
    )
    bio = db.Column(db.Text, nullable=True, comment="Apresentação profissional")
    specializations = db.Column(
        db.JSON,
        nullable=True,
        default=list,
        comment="Lista de especializações: ['Musculação', 'Funcional', ...]",
    )

    # --- Plano de assinatura ---
    plan = db.Column(
        db.String(20),
        nullable=False,
        default="starter",
        comment="starter | pro | elite",
    )
    plan_expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        comment="Null = sem expiração (período trial ou vitalício)",
    )

    # --- Políticas de agendamento ---
    session_duration = db.Column(
        db.Integer,
        nullable=False,
        default=60,
        comment="Duração padrão da sessão em minutos",
    )
    cancellation_hours_policy = db.Column(
        db.Integer,
        nullable=False,
        default=24,
        comment="Horas mínimas de antecedência para cancelamento sem custo",
    )

    # --- Configuração financeira ---
    pix_key = db.Column(
        db.String(150),
        nullable=True,
        comment="Chave PIX do trainer para recebimento de mensalidades",
    )

    # --- Disponibilidade semanal ---
    # Formato JSON: {"1": [{"start":"08:00","end":"12:00"}], ..., "7": [...]}
    # Chaves = isoweekday (1=seg, 7=dom). Valor = lista de blocos de horário.
    # None = não configurado (usa default: seg-sex 06:00–22:00).
    availability = db.Column(
        db.JSON,
        nullable=True,
        default=None,
        comment="Grade de disponibilidade semanal em JSON",
    )

    # --- Relacionamentos ---
    students = db.relationship(
        "Student",
        back_populates="trainer",
        lazy="dynamic",
        foreign_keys="Student.trainer_id",
    )
    appointments = db.relationship(
        "Appointment",
        back_populates="trainer",
        lazy="dynamic",
        foreign_keys="Appointment.trainer_id",
    )
    payments = db.relationship(
        "Payment",
        back_populates="trainer",
        lazy="dynamic",
        foreign_keys="Payment.trainer_id",
    )

    # --- Serialização ---
    def to_dict(self) -> dict:
        """Estende o to_dict do User com campos do Trainer."""
        data = super().to_dict()
        data.update(
            {
                "cref": self.cref,
                "bio": self.bio,
                "specializations": self.specializations or [],
                "plan": self.plan,
                "plan_expires_at": (
                    self.plan_expires_at.isoformat() if self.plan_expires_at else None
                ),
                "session_duration": self.session_duration,
                "cancellation_hours_policy": self.cancellation_hours_policy,
                "availability": self.availability,
                "pix_key": self.pix_key,
            }
        )
        return data

    def __repr__(self) -> str:
        return f"<Trainer {self.email} plano={self.plan}>"
