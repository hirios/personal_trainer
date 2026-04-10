# FitFlow Pro — Guia de Deploy em Produção

## 1. Pré-requisitos no servidor

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (para rate limiting e cache)
- Nginx (proxy reverso)
- Certbot (SSL/HTTPS)
- Git

---

## 2. Variáveis de ambiente (`.env` de produção)

Crie o arquivo `backend/.env` no servidor **nunca commite este arquivo no Git**.

```env
# ── Ambiente ──────────────────────────────────────────────────────────
FLASK_ENV=production

# Gere com: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=gere-uma-chave-forte-aqui

# ── Banco de dados (PostgreSQL) ───────────────────────────────────────
DATABASE_URL=postgresql://fitflow_user:senha_forte@localhost:5432/fitflow_pro

# ── JWT ───────────────────────────────────────────────────────────────
# Gere com: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=gere-outra-chave-forte-aqui

# ── CORS (apenas seu domínio real) ────────────────────────────────────
CORS_ORIGINS=https://app.seudominio.com.br

# ── Rate Limiting (Redis) ─────────────────────────────────────────────
RATELIMIT_STORAGE_URL=redis://localhost:6379/0

# ── E-mail (ex: SendGrid, SES, ou SMTP próprio) ───────────────────────
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=apikey
MAIL_PASSWORD=sua-api-key-sendgrid
MAIL_DEFAULT_SENDER=FitFlow Pro <noreply@seudominio.com.br>

# ── Asaas (Pagamentos) ────────────────────────────────────────────────
ASAAS_API_KEY=sua-chave-asaas-producao
ASAAS_ENVIRONMENT=production

# ── Z-API (WhatsApp) ──────────────────────────────────────────────────
ZAPI_INSTANCE_ID=seu-instance-id
ZAPI_TOKEN=seu-token
ZAPI_CLIENT_TOKEN=seu-client-token

# ── Anthropic (IA) ────────────────────────────────────────────────────
ANTHROPIC_API_KEY=sua-chave-anthropic
```

---

## 3. Banco de dados — setup inicial

### 3.1 Criar banco e usuário no PostgreSQL

```bash
sudo -u postgres psql

CREATE DATABASE fitflow_pro;
CREATE USER fitflow_user WITH PASSWORD 'senha_forte';
GRANT ALL PRIVILEGES ON DATABASE fitflow_pro TO fitflow_user;
\q
```

### 3.2 Remover o `db.create_all()` automático do factory

Antes do deploy, edite `backend/app/__init__.py` e **remova** o bloco:

```python
# REMOVA este bloco antes do deploy em produção:
if app.config.get("DEBUG") or app.config.get("TESTING"):
    with app.app_context():
        db.create_all()
```

Em produção, as tabelas são sempre criadas e atualizadas via Flask-Migrate.

### 3.3 Inicializar e aplicar as migrações

```bash
cd backend

# Apenas na primeira vez — cria a pasta migrations/
flask db init

# Gera o script de migração a partir dos models
flask db migrate -m "initial schema"

# Aplica as migrações no banco de dados
flask db upgrade
```

> **Para cada novo módulo** que adicionar models, rode:
> ```bash
> flask db migrate -m "descricao da mudanca"
> flask db upgrade
> ```

---

## 4. Instalar dependências de produção

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

---

## 5. Rodar com Gunicorn

```bash
# Teste manual (4 workers, porta 5000)
gunicorn -w 4 -b 127.0.0.1:5000 "run:app"

# Com logs detalhados
gunicorn -w 4 -b 127.0.0.1:5000 \
  --access-logfile /var/log/fitflow/access.log \
  --error-logfile  /var/log/fitflow/error.log \
  "run:app"
```

**Regra para número de workers:** `(2 × núcleos_da_CPU) + 1`

---

## 6. Systemd — manter o app rodando

Crie `/etc/systemd/system/fitflow.service`:

```ini
[Unit]
Description=FitFlow Pro — Flask API
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/fitflow-pro/backend
EnvironmentFile=/var/www/fitflow-pro/backend/.env
ExecStart=/var/www/fitflow-pro/backend/venv/bin/gunicorn \
    -w 4 -b 127.0.0.1:5000 \
    --access-logfile /var/log/fitflow/access.log \
    --error-logfile  /var/log/fitflow/error.log \
    "run:app"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable fitflow
sudo systemctl start fitflow
sudo systemctl status fitflow   # verificar se está rodando
```

---

## 7. Nginx — proxy reverso + SSL

Crie `/etc/nginx/sites-available/fitflow`:

```nginx
server {
    listen 80;
    server_name app.seudominio.com.br;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.seudominio.com.br;

    ssl_certificate     /etc/letsencrypt/live/app.seudominio.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.seudominio.com.br/privkey.pem;

    # Frontend estático
    root /var/www/fitflow-pro/frontend;
    index public/login.html;

    # API — proxy para o Gunicorn
    location /api/ {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Cache para assets estáticos
    location ~* \.(css|js|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/fitflow /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### SSL com Certbot

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d app.seudominio.com.br
# Certbot configura renovação automática via cron
```

---

## 8. Atualizar a URL da API no frontend

Antes de subir o frontend para produção, altere a linha em cada HTML que contém:

```javascript
window.API_BASE_URL = "http://localhost:5000";
```

Para:

```javascript
window.API_BASE_URL = "https://app.seudominio.com.br";
```

Ou, melhor ainda, use um arquivo de configuração centralizado:

```javascript
// frontend/js/config.js
window.API_BASE_URL = "https://app.seudominio.com.br";
```

E substitua todos os `window.API_BASE_URL = "..."` inline por:

```html
<script src="/js/config.js"></script>
```

---

## 9. Checklist pré-deploy

- [ ] `SECRET_KEY` e `JWT_SECRET_KEY` são strings aleatórias longas (≥ 32 bytes)
- [ ] `FLASK_ENV=production` (desativa o debug)
- [ ] `CORS_ORIGINS` aponta apenas para o domínio real (sem `*`)
- [ ] `DATABASE_URL` aponta para PostgreSQL (não SQLite)
- [ ] `RATELIMIT_STORAGE_URL` aponta para Redis
- [ ] Bloco `db.create_all()` removido do `__init__.py`
- [ ] `flask db upgrade` executado no banco de produção
- [ ] Arquivo `.env` **não está** no repositório Git (verificar `.gitignore`)
- [ ] SSL/HTTPS configurado e funcionando
- [ ] `window.API_BASE_URL` atualizado em todos os HTMLs do frontend
- [ ] Logs configurados e acessíveis

---

## 10. `.gitignore` recomendado

Certifique-se de que estes itens estão no `.gitignore` da raiz do projeto:

```
# Ambiente
backend/.env
backend/venv/
backend/__pycache__/
backend/**/__pycache__/
backend/**/*.pyc

# Banco de dados SQLite (apenas desenvolvimento)
backend/*.db
backend/instance/

# Migrações geradas localmente (commite apenas após revisar)
# Remova a linha abaixo se quiser versionar as migrações:
# backend/migrations/versions/
```

---

## 11. Backup do banco de dados

Configure um cron diário no servidor:

```bash
# crontab -e
0 3 * * * pg_dump -U fitflow_user fitflow_pro | gzip > /backups/fitflow_$(date +\%Y\%m\%d).sql.gz
# Manter apenas os últimos 30 dias
0 4 * * * find /backups -name "fitflow_*.sql.gz" -mtime +30 -delete
```
