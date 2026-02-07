# PLATAFORMA NR-1 (SaaS Multi-Tenant)

Inicializacao base do projeto com Django (backend), PostgreSQL e frontend em Vite.

## Stack

- Python 3.13
- Django 6.0.1
- PostgreSQL (via `psycopg`)
- Node.js 20+ (frontend)
- Vite 5

## Estrutura de pastas

```text
cissconsult/
|-- ciss_gestao/          # Configuracao Django (settings, urls, wsgi/asgi)
|-- apps/                 # Apps Django de dominio (multi-tenant)
|-- templates/            # Templates globais
|-- static/               # Arquivos estaticos de desenvolvimento
|-- media/                # Uploads locais
|-- frontend/             # App frontend (Vite)
|-- requirements/
|   |-- base.txt
|   `-- dev.txt
|-- manage.py
|-- .env.example
`-- README.md
```

## Variaveis de ambiente

Copie o exemplo:

```powershell
Copy-Item .env.example .env
```

Principais variaveis:

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_TIME_ZONE`
- `TENANCY_COMPANY_HEADER`
- `DB_ENGINE`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`

## Setup backend

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements\dev.txt
python manage.py migrate
python manage.py runserver
```

## Setup frontend

```powershell
cd frontend
npm install
npm run dev
```

Estrutura base reutilizavel do frontend:

- `frontend/src/config/env.js` (variaveis `VITE_*`)
- `frontend/src/services/http.js` (cliente HTTP com `X-Company-Id`)
- `frontend/src/components/` (componentes reutilizaveis)
- `frontend/src/layouts/` (shell de pagina)
- `frontend/src/styles/` (tokens, base, layout, componentes, utilitarios)

Telas basicas entregues:

- `#/login` (login inicial)
- `#/dashboard` (tela inicial com cards)
- `#/companies` (seletor de empresa ativa)
- Sidebar com navegacao e acao de logout

## Observacoes para multi-tenant

- A pasta `apps/` foi reservada para apps de dominio e isolamento por tenant.
- O banco padrao foi preparado para PostgreSQL via variaveis de ambiente.
- A estrategia adotada e multi-tenant logico (row-based) via `company_id`.

## Arquitetura SaaS Multi-Tenant (Task 1.2)

- O app `apps.tenancy` centraliza o modelo `Company`, middleware e contexto de tenant.
- Todas as entidades de negocio devem herdar de `TenantModel` (`apps/tenancy/models.py`), que define `company` obrigatorio (`company_id`) e timestamps.
- O manager padrao (`objects`) aplica filtro automatico por tenant com base no contexto da requisicao. Para acessos administrativos, use `all_objects`.
- O middleware `CompanyContextMiddleware` exige o header `X-Company-Id` (configuravel por `TENANCY_COMPANY_HEADER`) e injeta `request.company_id`.
- Rotas isentas de header estao em `TENANCY_EXEMPT_PATH_PREFIXES` (admin, healthz, static, media).
- Ha uma validacao automatica (`tenancy.E001`) que impede modelos concretos em `apps.*` sem campo `company`.
- O vinculo entre `auth_user` e empresa e feito por `company_memberships`.
- A sessao guarda a empresa ativa em `request.session['company_id']`.
- O middleware prioriza empresa da sessao para usuarios autenticados (nao confia apenas em header).

### Exemplo de acesso isolado

1. Crie uma empresa no admin (`/admin/`) em `Company`.
2. Em qualquer endpoint protegido, envie o header `X-Company-Id: <id_da_empresa>`.
3. Consultas com `Model.objects.all()` retornam somente dados da empresa ativa no contexto.

### Fluxo de login por empresa

1. Crie usuario em `/admin/auth/user/`.
2. Crie vinculo em `/admin/tenancy/companymembership/` entre usuario e empresa.
3. Faça login em `/auth/login/`.
4. Se houver mais de uma empresa vinculada, selecione em `/auth/select-company/`.

## Modelagem do banco (Task 2.1)

Tabelas modeladas:

- `companies` (`apps.tenancy.models.Company`)
- `users` (`apps.core.models.User`)
- `mood_records` (`apps.core.models.MoodRecord`)
- `risk_indicators` (`apps.core.models.RiskIndicator`)
- `complaints` (`apps.core.models.Complaint`)
- `support_actions` (`apps.core.models.SupportAction`)
- `alerts` (`apps.core.models.Alert`)
- `reports` (`apps.core.models.Report`)

Regras aplicadas:

- Todas as tabelas de dominio usam `company_id` obrigatorio via heranca de `TenantModel`.
- Coletas anonimas (`mood_records`, `complaints`) nao possuem campos pessoais e possuem restricao de anonimato.
- Padronizacao de data e periodo com os campos `record_date`, `period_start` e `period_end`.

## Gestao de usuarios por empresa (Task 3.2)

- CRUD de acessos internos por empresa em:
  - `GET /users/`
  - `GET/POST /users/new/`
  - `GET/POST /users/<membership_id>/edit/`
  - `POST /users/<membership_id>/delete/`
- Associacao de usuarios a papeis via `company_memberships.role`.
- Papeis disponiveis: `ADMIN_EMPRESA`, `GESTOR`, `RH`, `COLABORADOR`.
- Apenas usuarios com papel `ADMIN_EMPRESA` (ou `OWNER` legado) podem gerenciar acessos.

## Coleta Totem + monitoramento inicial (proximo passo iniciado)

- Totem por empresa:
  - `GET /totem/<company_slug>/<totem_slug>/`
  - `POST /totem/<company_slug>/<totem_slug>/mood/`
  - `POST /totem/<company_slug>/<totem_slug>/complaint/`
- Coleta anonima sem dados pessoais para humor e denuncia.
- Fluxo simplificado para tablet/tela cheia:
  - passo 1: escolher entre "Canal de denuncia" ou "Registrar humor";
  - passo 2: selecionar opcao em botoes grandes e confirmar.
- Dashboard interno agora mostra indicadores basicos dos ultimos 30 dias:
  - volume de humor,
  - denuncias criticas,
  - sentimento predominante.
  - graficos interativos (distribuicao, linha do tempo, frequencia semanal e comparativo de periodos).
  - grafico de quantidade de registros por totem.

## Controle por totem

- Gestao de totens por empresa (ADMIN_EMPRESA):
  - `GET /totems/`
  - `POST /totems/new/`
  - `POST /totems/<totem_id>/edit/`
  - `POST /totems/<totem_id>/delete/`
- Cada registro de humor/denuncia pode ser vinculado a um totem.
- Dashboard mostra contagem separada por totem no periodo selecionado.
"# cissconsult" 
"# cissconsult" 
