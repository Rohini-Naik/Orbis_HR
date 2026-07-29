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

## Quick start

**Linux / macOS**
```bash
git clone <your-repo-url> Orbis_HR
cd Orbis_HR
./setup.sh          # installs everything, sets up the database, creates your admin
./start.sh          # runs the backend and frontend together
```

**Windows** (Command Prompt or PowerShell — or just double-click the files)
```bat
git clone <your-repo-url> Orbis_HR
cd Orbis_HR
setup.bat
start.bat
```

Open **<http://localhost:5173>** and sign in with the admin account `setup.sh`
created for you. That's the whole install.

**You need installed first:** Python 3.11+, Node.js 20+, MySQL 8 (running), and a
free [Groq API key](https://console.groq.com/keys) — setup will ask you to paste
it. (Hugging Face is supported too; set `LLM_PROVIDER=huggingface` and
`HUGGINGFACE_API_KEY` in `.env`.)

> **Setting up on a second machine?** Everything above is all you need — but note
> that `.env` and the search index are deliberately *not* in git, so setup
> recreates them. You will be asked for your own Groq key and for the MySQL root
> password on that machine. See **Running it on another machine** below.

Setup is safe to re-run: it skips anything already done. It generates your
database password automatically and writes it to `.env` (never committed).

Both entry points run the same `setup.py`, so Windows and Unix behave
identically. The platform differences it handles for you:

| | Linux / macOS | Windows |
|---|---|---|
| MySQL root | `sudo mysql` (socket auth) | `mysql -u root -p`, prompts for the password |
| Virtualenv | `venv/bin/` | `venv\Scripts\` |
| PyTorch | `requirements.txt` | CPU-only wheel + `requirements-windows.txt` (avoids a multi-GB CUDA download) |

<details>
<summary>What setup.sh does, if you'd rather run the steps yourself</summary>

```bash
# 1. Configuration — copy the template and fill in your HF token + a DB password
cp .env.example .env
echo "VITE_API_BASE_URL=http://localhost:8000" > Frontend/.env

# 2. Backend dependencies
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Databases (sudo, because local MySQL root uses socket auth). Replace
#    __SET_A_STRONG_PASSWORD__ in each script with the password from your .env.
sudo mysql --local-infile=1 < scripts/bootstrap_local_mysql.sql
sudo mysql < scripts/bootstrap_app_mysql.sql
sudo mysql < scripts/bootstrap_hr_admin_mysql.sql
sudo mysql < scripts/migrate_employee_identity.sql

# 4. Company email addresses (each employee's login identity)
python -m app.provision backfill-emails

# 5. Policy search index (downloads the embedding model, ~440 MB, once)
python -m rag_engine.maintenance

# 6. Frontend dependencies
cd Frontend && npm install && cd ..

# 7. First administrator
python -m app.provision create-admin --email you@orbis.com
```

Then run the two servers in separate terminals:
`uvicorn app.main:app --reload --port 8000` and `cd Frontend && npm run dev`.

</details>

---

## Running it on another machine

A fresh clone deliberately does **not** carry your `.env`, your database, or the
search index — secrets must not be in git, and the index is a build artefact.
Setup recreates all three.

**1. Install the prerequisites**

| | |
|---|---|
| Python 3.11+ | <https://www.python.org/downloads/> (on Windows tick *Add Python to PATH*) |
| Node.js 20+ | <https://nodejs.org> |
| MySQL 8 | make sure the server is actually running |
| Groq API key | free at <https://console.groq.com/keys> |

**2. Clone and run setup**

```bash
git clone https://github.com/Rohini-Naik/Orbis_HR.git
cd Orbis_HR
./setup.sh          # Windows: setup.bat
```

It will ask for two things: your **Groq API key**, and your **MySQL root
password** (on Linux it usually uses `sudo` instead). Everything else — the
database password, the `.env` file, the Python and npm packages, the employee
data and the search index — it handles itself.

First run takes a few minutes: it downloads the embedding model (~440 MB) and
installs dependencies.

**3. Create your administrator**

Setup prompts for this at the end. If you skipped it:

```bash
source venv/bin/activate            # Windows: venv\Scripts\activate
python -m app.provision list-admins
python -m app.provision create-admin --email rohit.verma@orbis.com
```

Any company address from the `employees` table works. To see some:
`SELECT FullName, Email FROM employees LIMIT 5;`

**4. Start it**

```bash
./start.sh          # Windows: start.bat
```

Then open <http://localhost:5173>.

**5. Check it works**

```bash
python -m tests.e2e_check --admin-email you@orbis.com --admin-password 'yours'
```

45 checks against the running system. Add `--quick` to skip the ones that call
the AI.

### If something goes wrong

| Symptom | Cause and fix |
|---|---|
| `mysql client not found` | MySQL isn't on PATH. Windows: add `C:\Program Files\MySQL\MySQL Server 8.0\bin` |
| `Could not get administrative access to MySQL` | The server isn't running (`sudo systemctl start mysql`) or the root password was wrong |
| `ABORT: password placeholder not substituted` | A bootstrap `.sql` was run by hand. Use `./setup.sh`, which substitutes it |
| Chat replies "Hi! I'm Orbis" to every question | `GROQ_API_KEY` is missing or invalid — the real error is in the backend terminal |
| `employees table is missing [...]` | The table predates this version. Re-run setup to rebuild it |
| Frontend loads but every call fails | Backend isn't running, or `VITE_API_BASE_URL` in `Frontend/.env` is wrong |

Setup is safe to re-run at any point; it skips work already done.

---

### Creating the first administrator

No accounts are seeded — nothing ships with a known password. Create the first
HR admin on the machine (it prompts for a password):

```bash
source venv/bin/activate
python -m app.provision create-admin --email hr.head@orbis.com
```

Use any company address from the `employees` table; list a few with the
`Employees` tab, or query `SELECT EmployeeName, Email FROM employees LIMIT 5`.

### How people get accounts

| Who | How |
|-----|-----|
| **New hires** | An admin adds them under **Employees**. Orbis mints their company address and emails a single-use setup link to their **personal** inbox. |
| **Existing staff** | **Activate your account** on the login screen, using the company address HR issued. Addresses not on the HR system are refused. |
| **New HR admins** | An existing admin grants access under **Users & Access**. |

With `EMAIL_BACKEND=console` (the default) the invitation is printed to the
backend terminal instead of being sent — copy the link from there.

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
