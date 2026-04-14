"""
Model de solicitação de avaliação pelo aluno — AssessmentRequest.
O aluno envia uma solicitação com suas medidas; o trainer aprova (cria
a avaliação oficial) ou rejeita. Apenas uma solicitação pendente por vez.
"""
import uuid
from datetime import datetime, timezone
from app.extensions import db


def _uuid_str() -> str:
    return str(uuid.uuid4())


class AssessmentRequest(db.Model):
    """
    Solicitação de avaliação enviada pelo aluno.
    Status: pending → approved | rejected | cancelled
    """

    __tablename__ = "assessment_requests"

    id = db.Column(db.String(36), primary_key=True, default=_uuid_str)
    student_id = db.Column(
        db.String(36), db.ForeignKey("students.id"), nullable=False, index=True
    )
    trainer_id = db.Column(
        db.String(36), db.ForeignKey("trainers.id"), nullable=False, index=True
    )

    # Status do pedido
    status = db.Column(
        db.String(20), nullable=False, default="pending",
        comment="pending | approved | rejected | cancelled"
    )

    # Data sugerida pelo aluno
    date = db.Column(db.Date, nullable=False)

    # Medidas (todas opcionais)
    weight      = db.Column(db.Numeric(6, 2), nullable=True)
    height      = db.Column(db.Numeric(6, 2), nullable=True)
    body_fat    = db.Column(db.Numeric(5, 2), nullable=True)
    muscle_mass = db.Column(db.Numeric(6, 2), nullable=True)
    chest       = db.Column(db.Numeric(6, 2), nullable=True)
    waist       = db.Column(db.Numeric(6, 2), nullable=True)
    hip         = db.Column(db.Numeric(6, 2), nullable=True)
    abdomen     = db.Column(db.Numeric(6, 2), nullable=True)
    right_arm   = db.Column(db.Numeric(6, 2), nullable=True)
    left_arm    = db.Column(db.Numeric(6, 2), nullable=True)
    right_thigh = db.Column(db.Numeric(6, 2), nullable=True)
    left_thigh  = db.Column(db.Numeric(6, 2), nullable=True)
    right_calf  = db.Column(db.Numeric(6, 2), nullable=True)
    left_calf   = db.Column(db.Numeric(6, 2), nullable=True)
    notes       = db.Column(db.Text, nullable=True)

    # Fotos enviadas pelo aluno (array de URLs relativas, como em Assessment)
    photo_urls  = db.Column(db.JSON, nullable=True, default=list)

    # Timestamps
    created_at  = db.Column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)

    # Relacionamentos
    student = db.relationship("Student", foreign_keys=[student_id], lazy="select")
    trainer = db.relationship("Trainer", foreign_keys=[trainer_id], lazy="select")

    def to_dict(self) -> dict:
        def _f(val):
            return float(val) if val is not None else None

        return {
            "id":               self.id,
            "student_id":       self.student_id,
            "trainer_id":       self.trainer_id,
            "status":           self.status,
            "date":             self.date.isoformat() if self.date else None,
            "weight":           _f(self.weight),
            "height":           _f(self.height),
            "body_fat":         _f(self.body_fat),
            "muscle_mass":      _f(self.muscle_mass),
            "chest":            _f(self.chest),
            "waist":            _f(self.waist),
            "hip":              _f(self.hip),
            "abdomen":          _f(self.abdomen),
            "right_arm":        _f(self.right_arm),
            "left_arm":         _f(self.left_arm),
            "right_thigh":      _f(self.right_thigh),
            "left_thigh":       _f(self.left_thigh),
            "right_calf":       _f(self.right_calf),
            "left_calf":        _f(self.left_calf),
            "notes":            self.notes,
            "photo_urls":       self.photo_urls or [],
            "created_at":       self.created_at.isoformat() if self.created_at else None,
            "reviewed_at":      self.reviewed_at.isoformat() if self.reviewed_at else None,
            "rejection_reason": self.rejection_reason,
            "student_name":     self.student.name if self.student else None,
        }

    def __repr__(self) -> str:
        return f"<AssessmentRequest {self.id} student={self.student_id} status={self.status}>"
