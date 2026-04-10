# Prompt — Geração completa do FitFlow Pro

Cole este prompt inteiro em uma sessão do Claude (preferencialmente Claude Code ou Claude Sonnet com Projects). Execute módulo por módulo na ordem indicada.

---

## CONTEXTO GERAL (inclua sempre no início de cada sessão)

Você é um engenheiro full-stack sênior especializado em Flask e desenvolvimento web mobile-first. Estamos construindo o **FitFlow Pro**, um SaaS web para personal trainers brasileiros gerenciarem alunos, treinos, avaliações físicas, agendamentos, cobranças e comunicação — tudo em um único lugar.

### Stack obrigatória
- **Backend:** Python 3.12 + Flask 3.x
- **ORM:** SQLAlchemy 2.x + Flask-SQLAlchemy + Flask-Migrate (Alembic)
- **Banco (dev):** SQLite — a troca para PostgreSQL em produção deve exigir APENAS mudar a variável `DATABASE_URL`. Nenhuma outra linha de código pode mudar.
- **Auth:** Flask-JWT-Extended (access token 1h, refresh token 30 dias)
- **Frontend:** HTML5 + CSS3 + JavaScript ES2022 puro (sem frameworks JS)
- **CSS:** Tailwind CSS v3 via CDN no desenvolvimento
- **Ícones:** Lucide Icons via CDN
- **Gráficos:** Chart.js via CDN
- **Responsivo:** mobile-first obrigatório. Sidebar no desktop (lg+), bottom navigation fixa no mobile
- **Pagamentos:** Asaas API (Pix + recorrência)
- **WhatsApp:** Z-API (envio de mensagens automáticas)
- **IA:** Anthropic Claude API (geração de treinos)

### Princípios inegociáveis de código
1. Todo acesso ao banco passa pelo SQLAlchemy ORM — nunca SQL raw
2. Toda resposta de API segue o padrão `{"success": bool, "data": ..., "message": "..."}` com HTTP status correto
3. Todo endpoint protegido usa o decorator `@jwt_required()` + decorator customizado `@trainer_required` ou `@student_required`
4. Senhas sempre com `werkzeug.security.generate_password_hash` (bcrypt)
5. Variáveis de ambiente via `python-dotenv` — nunca hardcoded
6. Frontend: nenhum dado sensível no localStorage. Tokens JWT no `sessionStorage` ou cookie httpOnly
7. Tailwind usado para layout e espaçamento. CSS customizado apenas para componentes interativos específicos
8. Cada página HTML é autocontida: importa seus próprios scripts, não depende de ordem de carregamento global
9. Comentários em português no código (este produto é mantido por uma equipe brasileira)
10. Tratar todos os erros — nunca deixar exceção não capturada chegar ao usuário

### Estrutura de pastas (respeite sempre)
```
fitflow-pro/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── extensions.py
│   │   ├── models/
│   │   ├── routes/
│   │   ├── services/
│   │   └── utils/
│   ├── migrations/
│   ├── tests/
│   ├── .env.example
│   ├── requirements.txt
│   └── run.py
└── frontend/
    ├── trainer/         (área do personal trainer)
    ├── student/         (área do aluno — mobile-first)
    ├── public/          (landing page, login, cadastro)
    └── js/
        ├── api.js
        ├── auth.js
        └── components/
```

### Design system do frontend
```
Cores principais:
  Verde primário:  #22C55E  (--brand-primary)
  Verde escuro:    #15803D  (--brand-dark, hover)
  Laranja acento:  #F97316  (--brand-accent, alertas e destaques)
  Cinza base:      #F8FAFC  (--gray-50, fundo de página)
  Texto escuro:    #0F172A  (--gray-900)
  Texto muted:     #64748B  (--gray-500)
  Borda padrão:    #E2E8F0  (--gray-200)

Tipografia:
  Display/Headings: "Plus Jakarta Sans" (Google Fonts)
  Body:             "DM Sans" (Google Fonts)
  Monospace/números: "JetBrains Mono" (Google Fonts)

Border radius: cards=rounded-2xl, botões=rounded-xl, inputs=rounded-xl, badges=rounded-full
Sombras: cards usam shadow-sm + border border-gray-100. Nunca sombras pesadas.

Mobile layout (< 768px):
  - Sem sidebar
  - Header compacto: logo + avatar
  - Bottom nav fixa com 5 ícones: Home, Alunos, Agenda, Financeiro, Perfil
  - FAB verde (bottom-right) para ação primária da página

Desktop layout (>= 1024px):
  - Sidebar fixa 256px com logo, menu e avatar do PT na base
  - Conteúdo com max-w-7xl centralizado
  - Header com breadcrumb + botões de ação
```

---

## MÓDULO 1 — Base do projeto e autenticação

### O que gerar
Crie a estrutura base completa do projeto FitFlow Pro com autenticação funcional.

### Arquivos a criar

**`backend/requirements.txt`**
```
Flask==3.1.0
Flask-SQLAlchemy==3.1.1
Flask-Migrate==4.0.7
Flask-JWT-Extended==4.6.0
Flask-Mail==0.10.0
Flask-CORS==4.0.1
Flask-Limiter==3.8.0
SQLAlchemy==2.0.36
Werkzeug==3.1.3
python-dotenv==1.0.1
requests==2.32.3
anthropic==0.40.0
gunicorn==23.0.0
pytest==8.3.4
pytest-flask==1.3.0
```

**`backend/app/__init__.py`** — factory pattern com `create_app(config_name)`

**`backend/app/config.py`** — classes `DevelopmentConfig`, `ProductionConfig`, `TestingConfig` com:
- `SQLALCHEMY_DATABASE_URI` lendo de `DATABASE_URL` (SQLite default)
- JWT config (access 1h, refresh 30 dias)
- CORS origins configurável
- Flask-Limiter com Redis opcional (memory fallback)

**`backend/app/extensions.py`** — instâncias de `db`, `jwt`, `migrate`, `mail`, `cors`, `limiter`

**`backend/app/models/user.py`** — modelo base `User` com polimorfismo joined table:
- Campos: `id` (UUID), `name`, `email` (unique), `password_hash`, `role` (trainer/student), `phone`, `avatar_url`, `is_active`, `created_at`, `updated_at`

**`backend/app/models/trainer.py`** — herda `User`, campos: `cref`, `bio`, `specializations` (JSON), `plan` (starter/pro/elite), `plan_expires_at`, `session_duration`, `cancellation_hours_policy`

**`backend/app/models/student.py`** — herda `User`, campos: `trainer_id` (FK), `birth_date`, `gender`, `objective`, `health_notes`, `status` (active/inactive/pending_payment), `monthly_fee`, `payment_day`, `asaas_customer_id`, `access_token` (UUID único gerado no cadastro)

**`backend/app/utils/decorators.py`** — decorators `@trainer_required` e `@student_required` que injetam `current_trainer` ou `current_student` no kwargs

**`backend/app/routes/auth.py`** — blueprint `/api/auth` com:
- `POST /register` — cadastro de trainer (rate limit: 5/hora por IP)
- `POST /login` — retorna access_token + refresh_token
- `POST /refresh` — renova access_token via refresh_token
- `POST /logout` — invalida refresh_token no banco
- `GET /me` — dados do usuário logado

**`backend/run.py`** — entrada da aplicação

**`backend/.env.example`** — todas as variáveis necessárias comentadas

**`frontend/public/login.html`** — página de login com:
- Design premium usando o design system definido
- Formulário de email + senha com validação inline
- Link "Esqueci a senha"
- Link para cadastro
- Feedback visual de loading no botão durante chamada
- Redireciona para `trainer/index.html` após login bem-sucedido
- Armazena tokens no `sessionStorage`

**`frontend/public/register.html`** — cadastro do trainer com:
- Campos: nome completo, email, telefone, CREF (opcional), senha, confirmação de senha
- Validação em tempo real (email válido, senha mínima 8 chars, confirmação bate)
- Termos de uso (checkbox obrigatório)

**`frontend/js/api.js`** — módulo central de chamadas HTTP:
- `get(path, params)`, `post(path, body)`, `patch(path, body)`, `delete(path)`
- Adiciona `Authorization: Bearer <token>` automaticamente
- Se receber 401, tenta refresh automático via `/api/auth/refresh`
- Se refresh falhar, redireciona para login
- Expõe `Api.get`, `Api.post`, etc. como objeto global

**`frontend/js/auth.js`** — gerenciamento de sessão:
- `Auth.login(email, password)` — chama API, salva tokens, redireciona
- `Auth.logout()` — limpa storage, chama `/api/auth/logout`, redireciona
- `Auth.isLoggedIn()` — verifica se há token válido
- `Auth.getUser()` — retorna dados do usuário do storage
- Executa `Auth.isLoggedIn()` em toda página protegida, redireciona se não autenticado

**`frontend/js/components/toast.js`** — sistema de notificações:
- `Toast.success(msg)`, `Toast.error(msg)`, `Toast.warning(msg)`, `Toast.info(msg)`
- Aparece no canto inferior direito (desktop) / centralizado na base (mobile)
- Auto-fecha em 4 segundos com barra de progresso
- Animação de entrada e saída suave

**`frontend/js/components/modal.js`** — modal reutilizável:
- `Modal.open({ title, body, confirmLabel, onConfirm, cancelLabel })`
- `Modal.close()`
- Suporta conteúdo HTML no body
- Fecha ao clicar fora ou pressionar Esc
- Animação de entrada

**`frontend/js/components/layout.js`** — componente de layout compartilhado:
- Renderiza sidebar (desktop) com itens de menu ativos baseados na URL atual
- Renderiza bottom nav (mobile)
- Renderiza header com breadcrumb
- Função `initLayout(pageTitle, breadcrumbs)` chamada em cada página

---

## MÓDULO 2 — Gestão de alunos (dores 1, 3, 7)

### O que gerar

**`backend/app/models/`** — todos os models relacionados a alunos já definidos no módulo 1.

**`backend/app/routes/students.py`** — blueprint `/api/students`:
- `GET /` — lista alunos do trainer autenticado com filtros (`status`, `objective`, `search`, `overdue`) e paginação (`page`, `per_page=20`)
- `POST /` — cadastrar aluno (cria User + Student, gera `access_token` UUID único, envia email de boas-vindas)
- `GET /<id>` — perfil completo do aluno (join com último treino, última avaliação, próximo pagamento)
- `PATCH /<id>` — atualizar dados do aluno
- `DELETE /<id>` — desativar aluno (soft delete: `is_active=False`)
- `GET /public/<access_token>` — endpoint público sem auth: retorna dados básicos do aluno + treinos ativos (usado pela área do aluno)
- `GET /<id>/engagement` — score de engajamento: dias sem acessar, presença no mês, status de pagamento

**`frontend/trainer/students/index.html`** — lista de alunos:
- Grid de cards responsivo (1 col mobile, 2 col tablet, 3 col desktop)
- Cada card: foto/avatar com iniciais, nome, objetivo (badge colorido), status pagamento (indicador verde/amarelo/vermelho), dias desde último acesso
- Barra de busca com debounce 300ms
- Filtros: todos / ativos / inativos / inadimplentes / sem treino atualizado
- Ordenação: nome / último acesso / data de cadastro
- Estado vazio: ilustração + botão de cadastrar primeiro aluno
- FAB verde (mobile) e botão no header (desktop) para cadastrar aluno
- Click no card → navega para `detail.html?id=X`

**`frontend/trainer/students/new.html`** — formulário de cadastro:
- Wizard em 2 etapas (dados pessoais → dados do contrato)
- Etapa 1: foto (upload opcional), nome, email, telefone, data de nascimento, sexo, objetivo (select: emagrecimento/hipertrofia/condicionamento/saúde/reabilitação), observações de saúde
- Etapa 2: valor mensal, dia de vencimento, modalidade (presencial/online/híbrido), notas internas do PT
- Validação campo a campo ao sair do input (blur)
- Preview do link de acesso do aluno gerado automaticamente
- Botão "Copiar link" para mandar pro aluno

**`frontend/trainer/students/detail.html`** — perfil do aluno com abas:
- Header: foto, nome, objetivo, status, botões de ação rápida (mensagem, novo treino, nova avaliação)
- Score de engajamento visual (círculo com porcentagem colorido por nível)
- Aba 1 — Visão geral: dados pessoais editáveis inline, histórico resumido
- Aba 2 — Treinos: lista de fichas ativas e históricas com botão criar nova + botão duplicar de outra
- Aba 3 — Evolução: gráficos + fotos (implementado no módulo 4)
- Aba 4 — Agenda: próximas sessões + histórico (implementado no módulo 5)
- Aba 5 — Financeiro: cobranças do aluno com status (implementado no módulo 6)
- Aba 6 — Mensagens: chat interno (implementado no módulo 7)
- URL com hash para persistir aba ativa: `detail.html?id=X#workouts`

---

## MÓDULO 3 — Treinos e fichas (dores 1, 7, 10, 13)

### O que gerar

**`backend/app/models/workout.py`**:
- `Workout`: `id`, `student_id`, `trainer_id`, `title`, `description`, `category`, `is_active`, `starts_at`, `ends_at`, `created_at`
- `WorkoutExercise`: `id`, `workout_id`, `exercise_name`, `muscle_group`, `sets`, `reps`, `load`, `rest_seconds`, `technique_notes`, `video_url`, `position`, `superset_group`

**`backend/app/routes/workouts.py`** — blueprint `/api/workouts`:
- `GET /?student_id=X` — treinos de um aluno (filtro por `is_active`)
- `POST /` — criar ficha
- `GET /<id>` — detalhes com lista de exercícios ordenados por `position`
- `PATCH /<id>` — editar metadados da ficha
- `DELETE /<id>` — excluir (soft delete)
- `POST /<id>/exercises` — adicionar exercício
- `PATCH /<id>/exercises/<ex_id>` — editar exercício
- `DELETE /<id>/exercises/<ex_id>` — remover exercício
- `POST /<id>/exercises/reorder` — recebe array de `{id, position}` e atualiza posições em bulk
- `POST /<id>/duplicate` — duplica ficha: recebe `student_id` destino, copia todos os exercícios, retorna novo workout
- `GET /public/<workout_id>?token=<access_token>` — endpoint público para aluno ver o treino

**`frontend/trainer/workouts/builder.html`** — montador de treino:

Este é o componente mais importante do produto. Deve ter:

- Header do formulário: campo de nome da ficha, select de categoria, select de aluno (autocomplete), campos de data início/fim
- Seção de exercícios com estado vazio (ilustração + "Adicione o primeiro exercício")
- Lista de exercícios renderizada dinamicamente com:
  - Handle de drag & drop à esquerda (usando SortableJS via CDN: `https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js`)
  - Número de posição atualizado automaticamente ao reordenar
  - Campos inline editáveis: nome, grupo muscular (select), séries, reps, carga, descanso (segundos)
  - Campo de notas técnicas (textarea expansível)
  - Campo de URL do vídeo com preview embed quando é YouTube
  - Marcador de superset: toggle que agrupa com exercício anterior (borda colorida à esquerda)
  - Botão de remover exercício (com confirmação)
- Botão "Adicionar exercício" que abre modal de busca:
  - Input de busca com debounce 300ms
  - Busca em base de 200+ exercícios pré-cadastrados no frontend (JSON local) filtrados por nome e grupo muscular
  - Chips de filtro rápido por grupo: Peito, Costas, Ombro, Bíceps, Tríceps, Pernas, Abdômen, Cardio, Funcional
  - Click em exercício da lista → adiciona na ficha e fecha modal
  - Opção "Adicionar exercício personalizado" para nome livre
- Painel lateral "Gerar com IA" (toggle):
  - Exibe objetivo e nível do aluno selecionado automaticamente
  - Campo para o PT adicionar contexto livre ("foco em glúteos esta semana")
  - Campo de equipamentos disponíveis (checkboxes: barra, halteres, máquinas, elástico, peso corporal)
  - Botão "Gerar ficha completa" → chama `POST /api/ai/generate-workout` → insere exercícios gerados na lista
  - Estado de loading com skeleton durante geração
- Preview do link público ao lado (desktop) ou abaixo (mobile) do builder
- Botão "Salvar ficha" com loading state + redirect para detalhe do aluno após salvar

**`frontend/student/workout.html`** — área do aluno (mobile-first prioritário):
- Acesso via `/student/workout.html?token=<access_token>&workout=<id>`
- Design limpo tipo "cartão de treino" — sem menus ou distrações
- Header: logo do PT (se configurado) + nome do aluno + nome da ficha
- Navegação por exercício: um exercício por vez com setas ou swipe
- Cada exercício: nome grande, grupo muscular, série × reps × carga em destaque tipográfico
- Notas técnicas do PT em caixa destacada abaixo
- Botão "Ver vídeo" se houver URL (abre em modal fullscreen)
- Timer de descanso integrado: botão "Iniciar descanso" → countdown com som (beep no final) usando `AudioContext`
- Progresso da sessão: barra no topo (exercício X de Y)
- Marcação visual de superset (borda colorida)
- Botão "Concluí o treino" na última tela → animação de conclusão + confetti leve

**`frontend/js/components/workout-builder.js`** — lógica do builder:
- Estado local dos exercícios em array em memória
- Funções: `addExercise(data)`, `removeExercise(id)`, `updateExercise(id, fields)`, `reorderExercises(newOrder)`, `getPayload()`
- Integração com SortableJS: ao reordenar, atualiza posição no estado e chama API de reorder
- Debounce no auto-save: 2 segundos após última edição, salva automaticamente (PATCH silencioso)
- Indicador "Salvo automaticamente" no header

---

## MÓDULO 4 — Avaliação física e evolução (dores 4, 6)

### O que gerar

**`backend/app/models/assessment.py`**:
- Campos: `id`, `student_id`, `trainer_id`, `date`, `weight`, `height`, `body_fat`, `muscle_mass`, `bmi` (calculado), `chest`, `waist`, `hip`, `right_arm`, `left_arm`, `right_thigh`, `left_thigh`, `right_calf`, `left_calf`, `abdomen`, `notes`, `photo_urls` (JSON array de strings), `created_at`
- BMI calculado automaticamente via `@staticmethod` no modelo

**`backend/app/routes/assessments.py`** — blueprint `/api/assessments`:
- `GET /?student_id=X` — histórico de avaliações ordenado por data desc
- `POST /` — nova avaliação (calcula BMI automaticamente)
- `GET /<id>` — detalhes
- `PATCH /<id>` — corrigir avaliação
- `DELETE /<id>` — excluir
- `GET /progress/<student_id>` — endpoint específico para gráficos: retorna série temporal de `{date, weight, body_fat, waist, hip}` para Chart.js

**`backend/app/routes/uploads.py`** — blueprint `/api/uploads`:
- `POST /assessment-photo` — recebe arquivo de imagem, valida tipo (jpg/png/webp), valida tamanho (máx 10MB), salva em `uploads/assessments/<trainer_id>/`, retorna URL relativa
- Sanitiza nome do arquivo com `werkzeug.utils.secure_filename` + UUID prefix

**`frontend/trainer/students/detail.html`** — aba Evolução (complementar ao módulo 2):
- Gráfico de linha: peso ao longo do tempo (Chart.js, verde)
- Gráfico de linha: % gordura corporal ao longo do tempo (Chart.js, laranja)
- Gráfico de radar: medidas corporais (cintura, quadril, coxa, braço, abdômen) comparando primeira vs última avaliação
- Todos os gráficos responsivos com `maintainAspectRatio: false`
- Seção de fotos: grid de avaliações com foto de frente. Click → abre modal com comparador:
  - Select "Avaliação A" e "Avaliação B" no topo do modal
  - Slider de comparação (imagem A à esquerda, imagem B à direita, linha divisória arrastável)
  - Tabela de delta abaixo: cada medida com seta para cima/baixo colorida
- Resumo automático em linguagem natural: "Em 90 dias, [Nome] perdeu 4,2kg, 8cm na cintura e reduziu gordura corporal de 28% para 23,5%"
- Botão "Nova avaliação" → abre modal com formulário completo
- O formulário de avaliação no modal deve ter:
  - Campos agrupados por seção: "Composição corporal" | "Circunferências" | "Fotos" | "Notas"
  - Upload de até 4 fotos com preview e label editável (Frente, Costas, Lado D, Lado E)
  - BMI calculado e exibido em tempo real conforme peso e altura são digitados
  - Comparação com avaliação anterior ao lado de cada campo ("+2kg desde 15/01")

---

## MÓDULO 5 — Agendamentos (dora 5, 11)

### O que gerar

**`backend/app/models/appointment.py`**:
- Campos: `id`, `trainer_id`, `student_id`, `starts_at`, `ends_at`, `status` (scheduled/confirmed/completed/cancelled_trainer/cancelled_student/no_show), `location`, `notes`, `cancellation_reason`, `cancelled_at`, `created_at`

**`backend/app/routes/appointments.py`** — blueprint `/api/appointments`:
- `GET /?week=YYYY-WNN` — agenda da semana (retorna todos os appointments do trainer naquela semana)
- `POST /` — criar agendamento (valida conflito de horário)
- `GET /<id>` — detalhes
- `PATCH /<id>` — editar (hora, local, notas)
- `POST /<id>/cancel` — cancela com registro de motivo e `cancelled_at`
- `POST /<id>/complete` — marca como concluído
- `GET /available-slots?trainer_id=X&date=YYYY-MM-DD` — endpoint público: retorna horários disponíveis do trainer para um dia específico com base na grade de disponibilidade configurada
- `POST /book` — endpoint público: aluno agenda horário (recebe `access_token`, `starts_at`, `notes`)

**`backend/app/routes/trainer.py`** — blueprint `/api/trainer` (configurações):
- `GET /availability` — grade de disponibilidade semanal (JSON: dia da semana → array de blocos de horário)
- `PATCH /availability` — atualizar grade de disponibilidade
- `PATCH /profile` — atualizar perfil do trainer (bio, CREF, foto, duração de sessão, política de cancelamento)

**`frontend/trainer/schedule/index.html`** — agenda:

Desktop:
- Grade semanal (seg–dom) com eixo de horas (06h–22h)
- Cada appointment renderizado como bloco colorido na grade:
  - Verde: confirmado / Azul: agendado / Cinza: concluído / Vermelho: cancelado
  - Exibe nome do aluno e horário dentro do bloco
  - Click no bloco → modal de detalhes com botões de ação (confirmar, concluir, cancelar)
- Horários bloqueados (fora da disponibilidade) em cinza claro
- Click em horário vazio disponível → modal para criar agendamento
- Navegação por semana com botões ← →
- Botão "Hoje" para voltar à semana atual

Mobile:
- Visão de lista por dia (mais legível em tela pequena)
- Selector de data no topo (7 círculos de dias, clicável)
- Lista de agendamentos do dia selecionado em cards
- Swipe horizontal para mudar de dia

Configuração de disponibilidade:
- Seção na página de configurações: grade visual de dias × horários
- Toggle por bloco de hora para cada dia da semana
- Duração padrão de sessão (select: 30/45/60/90 min)

---

## MÓDULO 6 — Pagamentos e financeiro (dora 2, 9)

### O que gerar

**`backend/app/models/payment.py`**:
- Campos: `id`, `student_id`, `trainer_id`, `amount`, `due_date`, `paid_at`, `status` (pending/paid/overdue/cancelled), `payment_method`, `asaas_charge_id`, `pix_qr_code`, `pix_copy_paste`, `notes`, `created_at`

**`backend/app/routes/payments.py`** — blueprint `/api/payments`:
- `GET /?student_id=X&month=YYYY-MM&status=X` — histórico com filtros
- `POST /` — criar cobrança manual (sem Asaas, só registra no banco)
- `POST /bulk` — gera cobranças para todos os alunos ativos do trainer que não têm cobrança no mês vigente. Retorna `{created: N, skipped: N, errors: []}`
- `GET /<id>` — detalhes com QR code se disponível
- `POST /<id>/mark-paid` — marca como pago manualmente (recebe `payment_method`, `notes`)
- `DELETE /<id>` — cancelar cobrança (soft: `status=cancelled`)
- `GET /dashboard` — endpoint analítico: `{mrr_current, mrr_projected, total_overdue, total_pending, total_paid_month, students_overdue: [...], mrr_history: [{month, amount}×6]}`
- `POST /webhooks/asaas` — recebe payload do Asaas, valida token no header `asaas-access-token`, atualiza status do payment correspondente pelo `asaas_charge_id`

**`backend/app/services/payment_service.py`**:
- `create_customer(student)` → chama Asaas POST `/customers`, salva `asaas_customer_id` no aluno
- `create_pix_charge(student, amount, due_date)` → POST `/payments` no Asaas, salva QR code e copy-paste
- `generate_monthly_charges(trainer_id)` → itera alunos ativos, cria customer no Asaas se necessário, cria cobrança Pix para os que não têm cobrança do mês
- Todo request ao Asaas: header `access_token: {ASAAS_API_KEY}`. Usa sandbox URL se `FLASK_ENV=development`

**`frontend/trainer/payments/index.html`** — financeiro:

Dashboard superior (cards de métricas):
- MRR do mês atual (confirmado + pendente)
- Total já recebido no mês (verde)
- Total em aberto (amarelo)
- Total inadimplente (vermelho + quantidade de alunos)

Gráfico de barras: receita dos últimos 6 meses (Chart.js, verde)

Ação principal: botão "Gerar cobranças do mês" em destaque:
- Mostra preview: "X alunos ativos sem cobrança gerada para abril"
- Confirmação antes de executar
- Loader com progresso durante geração em lote
- Resultado: "12 cobranças geradas com sucesso. 2 erros — ver detalhes"

Lista de cobranças:
- Filtros: todos / pendentes / pagos / inadimplentes
- Busca por nome do aluno
- Ordenação por vencimento ou nome
- Cada linha: foto do aluno, nome, vencimento, valor, status (badge colorido), ações:
  - Ver QR Code Pix → abre modal com QR code grande + botão copiar código
  - Marcar como pago (abre mini-form: método de pagamento + data)
  - Reenviar lembrete por WhatsApp
  - Cancelar cobrança
- Paginação ou scroll infinito

---

## MÓDULO 7 — Comunicação interna (dor 8)

### O que gerar

**`backend/app/models/message.py`**:
- Campos: `id`, `trainer_id`, `student_id`, `sender_role` (trainer/student), `content`, `is_read`, `created_at`

**`backend/app/routes/messages.py`** — blueprint `/api/messages`:
- `GET /<student_id>` — histórico de mensagens da conversa com aluno, ordem `created_at ASC`, paginação com `before_id` para infinite scroll reverso
- `POST /` — enviar mensagem (trainer autenticado). Campos: `student_id`, `content`
- `POST /student` — endpoint público: aluno envia mensagem (auth via `access_token` no body)
- `PATCH /<student_id>/read` — marca todas as mensagens da conversa como lidas
- `GET /unread-count` — retorna total de mensagens não lidas agrupadas por aluno: `[{student_id, student_name, count}]`

**`frontend/trainer/students/detail.html`** — aba Mensagens (complementar ao módulo 2):
- Interface de chat clássica: mensagens do trainer à direita (verde), do aluno à esquerda (cinza)
- Timestamps relativos: "agora", "há 5 min", "ontem 14h30"
- Textarea de envio com `Ctrl+Enter` para enviar e `Enter` para quebrar linha
- Polling leve: verifica novas mensagens a cada 15 segundos quando a aba está ativa
- Ao abrir a aba, marca conversa como lida e remove badge do contador
- Badge de não lidas no selector de abas

**`frontend/student/index.html`** — home do aluno (mobile-first):
- Saudação: "Olá, [Nome]! Bom [manhã/tarde/noite]"
- Card do treino ativo com botão "Ver meu treino hoje"
- Card de próxima sessão agendada
- Card de mensagens não lidas do PT
- Botão flutuante para enviar mensagem ao PT

---

## MÓDULO 8 — Dashboard do trainer (dores 3, 9, 14)

### O que gerar

**`backend/app/routes/trainer.py`** — adicionar ao blueprint existente:
- `GET /dashboard` — endpoint principal do dashboard, retorna em um único request:
  - `students_active_count` — total de alunos ativos
  - `mrr_current` — MRR do mês
  - `overdue_count` — inadimplentes
  - `today_appointments` — array de agendamentos do dia (max 5)
  - `at_risk_students` — alunos sem acesso há 7+ dias com pagamento pendente
  - `students_without_workout` — alunos sem ficha ativa ou sem atualização há 30+ dias
  - `recent_activity` — últimas 10 ações: pagamentos recebidos, novos alunos, mensagens
  - `mrr_history` — array dos últimos 6 meses `{month, amount}`
  - `objectives_distribution` — contagem de alunos por objetivo (para gráfico donut)

**`frontend/trainer/index.html`** — dashboard:

Métricas superiores (grid 2×2 mobile, 4×1 desktop):
- Alunos ativos — número grande + "▲ 2 este mês" (delta verde/vermelho)
- MRR atual — R$ valor + comparativo com mês anterior
- Inadimplentes — número com badge vermelho se > 0
- Sessões hoje — número com horário da próxima

Seção "Hoje" — lista das sessões do dia com horário, foto e nome do aluno, status

Seção "Atenção necessária" (alertas proativos):
- Alunos sem acesso ao treino há 7+ dias (lista compacta com botão "Enviar mensagem")
- Alunos sem ficha ativa (botão "Criar treino")
- Alunos com pagamento vencido (botão "Ver cobrança")

Gráficos (lado a lado no desktop, empilhados no mobile):
- Gráfico de linha: MRR últimos 6 meses (Chart.js)
- Gráfico donut: distribuição de objetivos dos alunos (emagrecimento/hipertrofia/etc.)

Atividade recente — feed de eventos cronológico (pagamento recebido, novo aluno, mensagem)

---

## MÓDULO 9 — IA e notificações automáticas (dores 7, 10)

### O que gerar

**`backend/app/services/ai_service.py`**:
- `generate_workout(student_profile, trainer_context, available_equipment)`:
  - Monta prompt estruturado para o Claude com: objetivo do aluno, nível (iniciante/intermediário/avançado), restrições de saúde, equipamentos disponíveis, contexto adicional do PT
  - System prompt: especialista em educação física, retorna SEMPRE JSON com schema definido
  - Chama `anthropic.Anthropic().messages.create(model="claude-haiku-4-5-20251001", ...)`
  - Schema esperado: `{title, category, exercises: [{name, muscle_group, sets, reps, load, rest_seconds, technique_notes}]}`
  - Faz parse do JSON, valida schema, retorna como dict Python
  - Em caso de erro de parse: retorna erro descritivo (não propaga exceção crua)
- `suggest_variations(exercise_name, equipment_list)`:
  - Retorna array de 3–5 exercícios alternativos com mesmo foco muscular

**`backend/app/routes/ai.py`** — blueprint `/api/ai`:
- `POST /generate-workout` — recebe `student_id` + `equipment[]` + `context`, chama `ai_service.generate_workout`, retorna lista de exercícios prontos para inserir no builder
- `POST /suggest-variations` — recebe `exercise_name` + `equipment[]`, retorna sugestões

**`backend/app/services/whatsapp_service.py`**:
- `send_message(phone, text)` → POST para Z-API com instância e token do `.env`
- `send_payment_reminder(student, payment)` → template: "Olá {nome}! Seu plano de treino com {trainer} vence em {dias} dias. Acesse para pagar: {link_pix}"
- `send_overdue_notice(student, payment)` → template de cobrança vencida
- `send_workout_updated(student)` → "Seu treino foi atualizado! Acesse: {link}"
- `send_appointment_reminder(appointment)` → "Lembrete: você tem sessão com {trainer} hoje às {hora} em {local}"
- Todas as funções: silent fail com log de erro (não deve quebrar o fluxo principal)

**`backend/app/utils/scheduler.py`** — tarefas automáticas (APScheduler ou rota manual via cron):
- `run_daily_notifications()` — roda todo dia às 8h:
  - Busca pagamentos vencendo em 2 dias → envia lembrete WhatsApp
  - Busca pagamentos vencidos hoje → envia aviso de atraso
  - Busca sessões nas próximas 2h → envia lembrete
- `update_overdue_payments()` — muda status de `pending` para `overdue` se `due_date < hoje`

---

## MÓDULO 10 — Configurações, segurança e finalização

### O que gerar

**`frontend/trainer/settings/index.html`** — configurações em abas:
- Aba "Perfil": foto, nome, email, telefone, CREF, bio, especialidades (tags)
- Aba "Negócio": duração padrão de sessão, política de cancelamento, valor padrão de mensalidade, local padrão de atendimento
- Aba "Disponibilidade": grade visual de horários da semana (toggle por bloco de 1h)
- Aba "Notificações": toggles para ativar/desativar cada tipo de notificação WhatsApp
- Aba "Plano": plano atual, data de vencimento, botão de upgrade
- Aba "Segurança": alterar senha, revogar sessões ativas, excluir conta

**`backend/app/routes/auth.py`** — adicionar:
- `POST /change-password` — valida senha atual, aplica nova
- `POST /forgot-password` — gera token de reset (UUID + expiração 1h), envia email
- `POST /reset-password` — valida token, aplica nova senha, invalida token

**Segurança geral** — revisar e aplicar em todos os blueprints:
- `Flask-Limiter`: `/api/auth/login` → 10 req/min; `/api/auth/register` → 5 req/hora; `/api/ai/*` → 20 req/hora
- CORS: em produção, restringir `origins` ao domínio do frontend
- Validação de ownership: em TODO endpoint que recebe um ID de recurso, verificar se o recurso pertence ao trainer autenticado. Retornar 403 se não pertencer.
- Upload de arquivos: `magic bytes` validation (não confiar só na extensão), nome sanitizado com UUID prefix
- Todos os logs de erro com `app.logger.error(...)` incluindo traceback

**`backend/tests/`** — testes básicos de sanidade:
- `test_auth.py`: register, login, refresh, logout, token inválido retorna 401
- `test_students.py`: CRUD completo, filtros, acesso público via token
- `test_workouts.py`: criar, editar, reordenar, duplicar, acesso público
- `test_payments.py`: geração em bulk, webhook do Asaas, dashboard

**`README.md`** na raiz do projeto:
- Requisitos de sistema (Python 3.12+, Node.js opcional para build Tailwind)
- Instalação passo a passo (clone → venv → pip install → .env → flask db upgrade → flask run)
- Como configurar cada integração externa (Asaas, Z-API, Anthropic)
- Como rodar os testes
- Como fazer deploy no Railway (link para guia)
- Variáveis de ambiente documentadas com exemplo e descrição

---

## INSTRUÇÕES DE EXECUÇÃO

### Ordem recomendada
Execute um módulo por vez em sessões separadas. Comece sempre pela seção "CONTEXTO GERAL" colada antes do módulo.

```
Sessão 1: CONTEXTO GERAL + MÓDULO 1
Sessão 2: CONTEXTO GERAL + MÓDULO 2
Sessão 3: CONTEXTO GERAL + MÓDULO 3
Sessão 4: CONTEXTO GERAL + MÓDULO 4
Sessão 5: CONTEXTO GERAL + MÓDULO 5
Sessão 6: CONTEXTO GERAL + MÓDULO 6
Sessão 7: CONTEXTO GERAL + MÓDULO 7
Sessão 8: CONTEXTO GERAL + MÓDULO 8
Sessão 9: CONTEXTO GERAL + MÓDULO 9
Sessão 10: CONTEXTO GERAL + MÓDULO 10
```

### Prompt de abertura de cada sessão
Cole exatamente assim:

```
[CONTEXTO GERAL completo acima]

Agora implemente o [MÓDULO X] conforme especificado.
Gere todos os arquivos descritos com código completo e funcional.
Não use placeholders como "# implementar depois" ou "# TODO".
Cada arquivo deve estar pronto para rodar.
Quando terminar um arquivo, avance para o próximo sem perguntar.
```

### Se o modelo travar em um arquivo específico
```
Continue a partir do arquivo [nome do arquivo].
O que foi gerado antes está correto, não regere.
```

### Para validar cada módulo antes de avançar
```
Após gerar o módulo, me mostre:
1. Lista de todos os arquivos criados
2. Como testar as rotas principais com curl ou Postman
3. O que precisa estar configurado no .env para este módulo funcionar
4. Qualquer dependência de módulo anterior que precisa estar rodando
```

---

*Prompt gerado em Abril de 2026 para o projeto FitFlow Pro*
