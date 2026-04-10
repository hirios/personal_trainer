"""
Model Payment — cobranças mensais dos alunos.
Suporta criação manual e integração com Asaas (Pix + boleto).
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid_str() -> str:
    return str(uuid.uuid4())


class Payment(db.Model):
    """
    Representa uma cobrança vinculada a um aluno e seu trainer.

    Ciclo de vida:
      pending → paid         (pagamento confirmado)
      pending → overdue      (venceu sem pagamento — atualizado por job/webhook)
      pending → cancelled    (cancelado manualmente)
      overdue → paid         (pago em atraso)
      overdue → cancelled
    """

    __tablename__ = "payments"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=_uuid_str,
        comment="UUID v4 gerado automaticamente",
    )

    # --- Relacionamentos ---
    student_id = db.Column(
        db.String(36),
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trainer_id = db.Column(
        db.String(36),
        db.ForeignKey("trainers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # --- Valores ---
    amount = db.Column(
        db.Numeric(10, 2),
        nullable=False,
        comment="Valor da cobrança em BRL",
    )
    due_date = db.Column(
        db.Date,
        nullable=False,
        index=True,
        comment="Data de vencimento",
    )
    paid_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
        comment="Timestamp do pagamento confirmado",
    )

    # --- Status ---
    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | paid | overdue | cancelled",
    )

    # --- Detalhes do pagamento ---
    payment_method = db.Column(
        db.String(30),
        nullable=True,
        comment="pix | boleto | dinheiro | cartao | transferencia | outro",
    )
    notes = db.Column(
        db.Text,
        nullable=True,
        comment="Observações internas sobre o pagamento",
    )

    # --- Integração Asaas ---
    asaas_charge_id = db.Column(
        db.String(50),
        nullable=True,
        unique=True,
        comment="ID da cobrança no Asaas (ex: pay_xxxxxxxxxxxxxxxx)",
    )
    pix_qr_code = db.Column(
        db.Text,
        nullable=True,
        comment="QR code em base64 gerado pelo Asaas",
    )
    pix_copy_paste = db.Column(
        db.Text,
        nullable=True,
        comment="Código Pix copia-e-cola",
    )

    # --- Auditoria ---
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relacionamentos ORM ---
    student = db.relationship("Student", back_populates="payments", lazy="select")
    trainer = db.relationship("Trainer", back_populates="payments", lazy="select")

    # --- Serialização ---
    def to_dict(self, include_student: bool = True) -> dict:
        data = {
            "id": self.id,
            "student_id": self.student_id,
            "trainer_id": self.trainer_id,
            "amount": float(self.amount) if self.amount is not None else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "status": self.status,
            "payment_method": self.payment_method,
            "notes": self.notes,
            "asaas_charge_id": self.asaas_charge_id,
            "pix_qr_code": self.pix_qr_code,
            "pix_copy_paste": self.pix_copy_paste,
            "created_at": self.created_at.isoformat() if self.created_at else None,
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
        return data

    def __repr__(self) -> str:
        return f"<Payment {self.id[:8]} student={self.student_id[:8]} status={self.status}>"
