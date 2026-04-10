"""
Ponto de entrada da aplicação FitFlow Pro.
Uso: python run.py
Em produção: gunicorn -w 4 -b 0.0.0.0:5000 "run:app"
"""
import os
from app import create_app

# Lê o ambiente da variável FLASK_ENV (default: development)
config_name = os.environ.get("FLASK_ENV", "development")
app = create_app(config_name)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = config_name == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
