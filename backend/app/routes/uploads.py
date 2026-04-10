"""
Blueprint de uploads — /api/uploads
Recebe fotos de avaliação física e as serve via rota estática.
"""
import os
import uuid
from flask import Blueprint, request, jsonify, send_from_directory, current_app
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from app.utils.decorators import trainer_required

uploads_bp = Blueprint("uploads", __name__, url_prefix="/api/uploads")

# Tipos MIME aceitos
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXT  = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE_MB  = 10
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024


def _ok(data=None, message="", status=200):
    return jsonify({"success": True, "data": data, "message": message}), status


def _err(message="Erro", status=400):
    return jsonify({"success": False, "data": None, "message": message}), status


def _uploads_root() -> str:
    """Retorna o caminho absoluto da pasta raiz de uploads."""
    # Sobe dois níveis a partir de app/ → backend/
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "uploads")


# ------------------------------------------------------------------ #
#  POST /api/uploads/assessment-photo                               #
# ------------------------------------------------------------------ #

@uploads_bp.route("/assessment-photo", methods=["POST"])
@jwt_required()
@trainer_required
def upload_assessment_photo(**kwargs):
    """
    Recebe uma foto de avaliação física.
    - Valida tipo (jpg/png/webp) e tamanho (máx 10MB)
    - Salva em uploads/assessments/<trainer_id>/
    - Retorna a URL relativa para acesso via GET /api/uploads/files/<path>
    """
    trainer = kwargs["current_trainer"]

    if "photo" not in request.files:
        return _err("Nenhum arquivo enviado. Use o campo 'photo'.")

    file = request.files["photo"]

    if not file.filename:
        return _err("Nome de arquivo inválido.")

    # Valida extensão
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXT:
        return _err(f"Tipo de arquivo não permitido. Use: jpg, png ou webp.")

    # Valida MIME type
    if file.mimetype not in ALLOWED_MIME:
        return _err("Tipo MIME não permitido.")

    # Valida tamanho (lê até MAX+1 bytes para detectar excesso)
    file.seek(0, 2)  # vai ao fim
    size = file.tell()
    file.seek(0)     # volta ao início
    if size > MAX_SIZE_BYTES:
        return _err(f"Arquivo muito grande. Máximo: {MAX_SIZE_MB}MB.")

    # Monta caminho seguro: uploads/assessments/<trainer_id>/<uuid><ext>
    safe_name = f"{uuid.uuid4()}{ext}"
    subdir     = os.path.join("assessments", trainer.id)
    full_dir   = os.path.join(_uploads_root(), subdir)
    os.makedirs(full_dir, exist_ok=True)

    file_path = os.path.join(full_dir, safe_name)
    file.save(file_path)

    # URL relativa usada para buscar o arquivo depois
    relative_url = f"assessments/{trainer.id}/{safe_name}"

    return _ok(
        data={"url": relative_url},
        message="Foto enviada com sucesso.",
        status=201,
    )


# ------------------------------------------------------------------ #
#  GET /api/uploads/files/<path>                                     #
# ------------------------------------------------------------------ #

@uploads_bp.route("/files/<path:filepath>", methods=["GET"])
def serve_upload(filepath):
    """Serve arquivos de upload. Sem autenticação — URLs são UUIDs não adivinháveis."""
    uploads_root = _uploads_root()
    # Garante que o caminho não escapa da pasta de uploads (path traversal)
    abs_path = os.path.realpath(os.path.join(uploads_root, filepath))
    if not abs_path.startswith(os.path.realpath(uploads_root)):
        return _err("Acesso negado.", 403)

    directory = os.path.dirname(abs_path)
    filename  = os.path.basename(abs_path)
    return send_from_directory(directory, filename)
