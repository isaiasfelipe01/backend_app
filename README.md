# MeuFinanças

Aplicativo Android de consolidação financeira usando Pluggy/Open Finance, FastAPI e Supabase/PostgreSQL. O modo atual é pessoal e importa lançamentos exclusivamente da Pluggy; categorias, metas e edições de descrição/categoria são mantidas localmente.

## Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# preencha PLUGGY_CLIENT_ID, PLUGGY_CLIENT_SECRET, PLUGGY_WEBHOOK_SECRET
# e SUPABASE_SERVICE_ROLE_KEY
uvicorn app.main:app --reload
```

Execute as migrations na ordem `000_reset_legacy_explicit.sql` (destrutiva e autorizada para os dados antigos), `001_initial_schema.sql`, `002_pluggy_upsert.sql`, `003_api_functions.sql`, `004_pluggy_only_security.sql`, `005_financial_analytics.sql` e `006_atomic_upsert.sql`. O arquivo 000 não é executado pelo app e só deve ser usado na substituição autorizada do banco legado.

`X-User-ID` deve ser o `APP_USER_ID`. O backend usa somente a chave `service_role`; ela nunca vai para o Android. A API fica em `/docs`. Configure no painel Pluggy um webhook HTTPS para `POST /webhooks/pluggy` com o segredo em `PLUGGY_WEBHOOK_SECRET`.

Testes: `cd backend && .venv/bin/pytest -q`. Lint: `.venv/bin/ruff check app tests`.

## Android

Abra `android/` no Android Studio com JDK 17. Para apontar para outro backend:

```bash
cd android
./gradlew test assembleDebug -PAPI_URL=https://meu-financas-backend.vercel.app/
```

No emulador, o padrão é `http://10.0.2.2:8000/`; em aparelho físico use o IP da máquina. O APK debug gerado é `android/app/build/outputs/apk/debug/app-debug.apk` e há uma cópia em `MeuFinancas-debug.apk` na raiz. O app solicita notificações no Android 13+, agenda `unpaid_bills_reminder` a cada 12 horas e preserva o estado anterior se a API falhar.

## Deploy Vercel

O repositório deve ser importado com a **raiz do repositório** como Root Directory (não selecione `backend`), pois `vercel.json` aponta para `api/index.py`. Não é necessário configurar um comando Uvicorn para produção; a Vercel usa o builder `@vercel/python`. Cadastre no projeto Vercel todas as variáveis de `backend/.env.example` nos ambientes **Production** e **Preview**. O endpoint público é `https://meu-financas-backend.vercel.app/`.

Depois do deploy, valide `https://meu-financas-backend.vercel.app/health` e `.../docs`. O APK de produção já usa essa URL por padrão. Para desenvolvimento local, gere com `-PAPI_URL=http://10.0.2.2:8000/`.
