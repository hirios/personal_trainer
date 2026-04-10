"""
Serve os arquivos estáticos do frontend diretamente pelo Flask.
Permite rodar o projeto com apenas `python run.py`, sem Live Server.

A raiz `/` redireciona para a página de login.
Qualquer caminho `/frontend/<arquivo>` entrega o arquivo correspondente
da pasta frontend/ na raiz do repositório.
"""
import os
from flask import Blueprint, send_from_directory, redirect, url_for

frontend_bp = Blueprint("frontend", __name__)

# Caminho absoluto da pasta frontend/ (dois níveis acima de backend/app/)
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend")
)


@frontend_bp.route("/")
def index():
    """Redireciona a raiz para a página de login."""
    return redirect("/frontend/public/login.html")


@frontend_bp.route("/frontend/<path:filename>")
def serve_frontend(filename):
    """Entrega qualquer arquivo dentro de frontend/."""
    return send_from_directory(FRONTEND_DIR, filename)
