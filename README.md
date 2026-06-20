# Orbis — Agentic AI HR Compliance Co-pilot

Orbis is an on-premise AI assistant for HR. Employees and HR admins ask
natural-language questions and get **verified, cited answers**:

- **Policy questions** are answered with **RAG** over your uploaded policy documents.
- **HR-data questions** are answered with **NL→SQL** over the employee database.
- **Casual messages** ("hi", "what can you do") are handled as normal conversation.

Every question is auto-routed by an LLM, grounded-checked by a hallucination
filter, and recorded in an audit trail. Embeddings run **locally** (your document
text never leaves the machine); only the generative models are called via the
Hugging Face Inference API.

---

## Features

- 🤖 **AI Co-pilot** — LLM router → RAG / NL→SQL / chat, with conversation memory
- 📄 **Cited answers** — every policy answer shows source, section & confidence
- 🔒 **Employee data scoping** — employees can only ever see their *own* records
- 🛡️ **Hallucination filter** — ungrounded answers are blocked
- 👥 **Roles** — Employee vs HR Admin (email + password auth)
- 📚 **Policy Library** — upload / search / view / download / delete (auto-indexed)
- 🧑‍💼 **Employee management** — admins add/list/delete employee records
- 📋 **Audit log** — every action logged (privacy-safe) + CSV export
- 🎨 **React dashboard** — dark themed SPA

## Tech stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI (Python 3.11), MySQL, ChromaDB |
| AI | sentence-transformers (local embeddings), Hugging Face Inference API (LLM) |
| Frontend | React + TypeScript (Vite) |

---

## Prerequisites

Install these first:

- **Python 3.11+**
- **Node.js 20+** and npm
- **MySQL 8.x** (running locally)
- A **Hugging Face token** with the **"Make calls to Inference Providers"** permission
  — create one at <https://huggingface.co/settings/tokens>

---

## Installation (local)

### 1. Clone the repo

```bash
git clone <your-repo-url> Orbis_HR
cd Orbis_HR
```

### 2. Backend — Python environment

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Create your `.env`

Create a file named `.env` in the project root with:

```ini
# Hugging Face token (needs "Make calls to Inference Providers" permission)
HUGGINGFACE_API_KEY=hf_your_token_here

# MySQL — read-only HR data (used by NL→SQL)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=orbis_user
MYSQL_PASSWORD=Ovi@2021
MYSQL_DATABASE=orbis_hr

# MySQL — read-write app state (users, chats, audit) — isolated DB
MYSQL_APP_USER=orbis_app
MYSQL_APP_PASSWORD=Ovi@2021
MYSQL_APP_DATABASE=orbis_app

# MySQL — read-write HR-data admin (only the admin "Employees" tab)
MYSQL_HR_ADMIN_USER=orbis_hr_admin
MYSQL_HR_ADMIN_PASSWORD=Ovi@2021

# Models
EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5
HF_ANSWER_MODEL=meta-llama/Llama-3.1-8B-Instruct
HF_SQL_MODEL=meta-llama/Llama-3.1-8B-Instruct
```

### 4. Set up the MySQL databases

These scripts create the databases/users and load the employee data. Run them
once (they need `sudo` because the local MySQL `root` uses socket auth):

```bash
# Read-only HR DB + load the employees CSV
sudo mysql --local-infile=1 < scripts/bootstrap_local_mysql.sql

# Read-write app-state DB (users, sessions, conversations, audit)
sudo mysql < scripts/bootstrap_app_mysql.sql

# Read-write HR-admin user (for the admin "Employees" tab)
sudo mysql < scripts/bootstrap_hr_admin_mysql.sql
```

> The employee CSV lives in `database_data/`. If your MySQL root has a password,
> use `sudo mysql -u root -p …` instead.

### 5. Build the policy search index (ChromaDB)

This downloads the local embedding model (~400 MB, first time only) and indexes
the documents in `policy_documents/`:

```bash
source venv/bin/activate
python -m rag_engine.maintenance
```

### 6. Frontend — install dependencies

```bash
cd Frontend
npm install
cd ..
```

---

## Running the app

Open **two terminals** from the project root.

**Terminal 1 — backend API**
```bash
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```
API: <http://localhost:8000>  ·  interactive docs: <http://localhost:8000/docs>

**Terminal 2 — frontend**
```bash
cd Frontend
npm run dev
```
App: **<http://localhost:5173>**

Open <http://localhost:5173> in your browser.

### Demo accounts (seeded automatically, password `demo1234`)

| Email | Role | Access |
|-------|------|--------|
| `rohit.verma@acmecorp.com` | HR Admin | org-wide data, policy library, audit, employees |
| `priya.sharma@acmecorp.com` | Employee | only their own records + policies |

New employees can self-register from the **Create an account** link on login.

---

## How it works

```
Question ─▶ Router (LLM) ─▶ ┌ RAG engine    → cited policy answer
                            ├ NL→SQL engine → data answer (employees scoped to self)
                            └ Chat          → normal conversation
                                   │
                     Hallucination filter + Memory + Audit log
```

- **Privacy:** the audit log shows employee chat content **only for blocked entries**;
  normal activity is logged as metadata (who / when / route / status).
- **Read-only AI:** NL→SQL runs as a read-only DB user and only `SELECT` is allowed.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Address already in use` on port 8000 | `fuser -k 8000/tcp` then restart uvicorn |
| Chat returns `403` | Your HF token lacks the **Inference Providers** permission — edit the token |
| `Access denied for user 'orbis_*'` | Re-run the matching `scripts/bootstrap_*.sql` with `sudo` |
| Model download is slow/stalls | It's a one-time ~400 MB download; re-run `python -m rag_engine.maintenance` |
| Frontend can't reach API | Ensure backend is on `:8000` and `CORS_ORIGINS` includes `http://localhost:5173` |

## Project structure

```
Orbis_HR/
├── app/             # FastAPI backend (routers, services, auth, db)
├── rag_engine/      # AI engine (router, RAG, NL→SQL, embeddings, verifier, llm)
├── Frontend/        # React + TypeScript (Vite) dashboard
├── scripts/         # MySQL bootstrap + model-fetch helpers
├── policy_documents/# source policy files (indexed into ChromaDB)
├── database_data/   # employees CSV
└── requirements.txt
```
