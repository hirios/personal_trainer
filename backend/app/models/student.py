"""
Model Student — herda de User via joined-table inheritance.
Armazena dados específicos do aluno vinculado a um personal trainer.
"""
import uuid
from app.extensions import db
from .user import User


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Student(User):
    """
    Tabela complementar para alunos.
    Cada aluno pertence a um Trainer e possui um access_token
    único para acesso à área do aluno sem necessidade de senha.
    """

    __tablename__ = "students"

    __mapper_args__ = {
        "polymorphic_identity": "student",
    }

    # FK para a tabela base
    id = db.Column(db.String(36), db.ForeignKey("users.id"), primary_key=True)

    # --- Vínculo com o trainer ---
    trainer_id = db.Column(
        db.String(36),
        db.ForeignKey("trainers.id"),
        nullable=False,
        index=True,
    )
    trainer = db.relationship(
        "Trainer",
        back_populates="students",
        foreign_keys=[trainer_id],
    )

    # --- Dados pessoais ---
    birth_date = db.Column(db.Date, nullable=True)
    gender = db.Column(
        db.String(10),
        nullable=True,
        comment="male | female | other",
    )
    objective = db.Column(
        db.String(255),
        nullable=True,
        comment="Objetivo principal: emagrecimento, hipertrofia, condicionamento...",
    )
    health_notes = db.Column(
        db.Text,
        nullable=True,
        comment="Observações de saúde: lesões, restrições, medicamentos",
    )

    # --- Status e financeiro ---
    status = db.Column(
        db.String(20),
        nullable=False,
        default="active",
        comment="active | inactive | pending_payment",
    )
    monthly_fee = db.Column(
        db.Numeric(10, 2),
        nullable=True,
        comment="Mensalidade em reais (BRL)",
    )
    payment_day = db.Column(
        db.Integer,
        nullable=True,
        comment="Dia do mês para vencimento (1-28)",
    )

    # --- Integração Asaas ---
    asaas_customer_id = db.Column(
        db.String(50),
        nullable=True,
        comment="ID do cliente na plataforma Asaas",
    )

    # --- Modalidade de treino ---
    modality = db.Column(
        db.String(20),
        nullable=True,
        default="presencial",
        comment="presencial | online | híbrido",
    )

    # --- Notas internas do personal trainer ---
    internal_notes = db.Column(
        db.Text,
        nullable=True,
        comment="Anotações privadas do PT sobre o aluno (não visíveis ao aluno)",
    )

    # --- Acesso à área do aluno ---
    access_token = db.Column(
        db.String(36),
        unique=True,
        nullable=False,
        default=_uuid_str,
        comment="Token UUID único para acesso sem senha à área do aluno",
    )
    last_access_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        comment="Última vez que o aluno acessou a plataforma",
    )

    # --- Serialização ---
    def to_dict(self) -> dict:
        """Estende o to_dict do User com campos do Student."""
        data = super().to_dict()
        data.update(
            {
                "trainer_id": self.trainer_id,
                "birth_date": (
                    self.birth_date.isoformat() if self.birth_date else None
                ),
                "gender": self.gender,
                "objective": self.objective,
                "health_notes": self.health_notes,
                "status": self.status,
                "monthly_fee": float(self.monthly_fee) if self.monthly_fee else None,
                "payment_day": self.payment_day,
                "modality": self.modality,
                "internal_notes": self.internal_notes,
                "last_access_at": (
                    self.last_access_at.isoformat() if self.last_access_at else None
                ),
                "asaas_customer_id": self.asaas_customer_id,
                # access_token NÃO é exposto aqui — apenas em to_dict_with_token()
            }
        )
        return data

    def to_dict_with_token(self) -> dict:
        """Inclui access_token — use apenas em respostas autorizadas ao trainer."""
        data = self.to_dict()
        data["access_token"] = self.access_token
        return data

    def __repr__(self) -> str:
        return f"<Student {self.email} trainer={self.trainer_id}>"
