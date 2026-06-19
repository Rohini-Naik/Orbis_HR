# Orbis — Agentic AI HR Compliance Co-pilot

## What is this project?

Orbis is an AI-powered HR assistant that runs **inside your company's network** (on-premise). Employees can ask it questions about company policies or their personal HR data, and it gives back **verified, cited answers** — not random guesses.

Think of it as a smart HR helpdesk that works 24/7, knows all company policies, and can pull your personal data (leaves, appraisals, etc.) instantly.

---

## How does the AI work behind the scenes?

Every question goes through this pipeline:

1. **You ask a question** → typed into the chatbot
2. **Router LLM** → figures out what *kind* of question it is
3. **Two engines** pick up the work:
   - **RAG Engine** (for policy questions) — searches uploaded policy documents and finds the exact relevant section
   - **NL → SQL Engine** (for data questions) — converts your question into a database query and fetches your actual HR data
4. **Memory + Verification** → checks the answer against the source to block hallucinations
5. **Cited answer** → you get the response with the source document and section referenced

---

## Two Sides of the App

### 🟢 User Side (Employee)

When an employee logs in, they get:

- **AI Chatbot** — the main feature. Ask anything like:
  - *"How many casual leaves do I have left?"* (data query → hits the database)
  - *"What is the maternity leave policy?"* (policy query → searches uploaded policy PDFs)
  - *"When did I join and when is my next appraisal?"* (data query)
  - *"Can I claim reimbursement for a home office chair?"* (policy query)
- **Suggested questions** — pre-built quick prompts to get started
- **Source citations** — every answer shows which policy document and section it came from, plus a confidence score
- **SQL transparency** — if it ran a database query, you can see the exact SQL it used
- **Conversation history** — sidebar shows past chats
- **Memory** — the chatbot remembers context within a conversation

**Key point:** Employees can only see their *own* data. They cannot access org-wide or other employees' information.

---

### 🟠 Admin Side (HR Admin)

When an HR Admin logs in, they get **three tabs**:

#### Tab 1 — AI Co-pilot (Chatbot)
- Same chatbot as employees, but with **elevated access**
- Can ask **org-wide questions** like:
  - *"How many employees have pending POSH training?"*
  - *"Which department has the highest leave utilization?"*
- Sees aggregate data across the entire organization
- Every admin query is auto-logged for compliance

#### Tab 2 — Policy Library (File Management)
This is where admins manage the documents that power the AI:

- **Upload files** — drag-and-drop or browse (PDF, DOCX, TXT)
- **Auto-indexing** — once uploaded, the file is automatically chunked into pieces and embedded so the AI can search it
- **View files** — click to read the full policy document
- **Delete files** — remove a policy, which un-indexes it from the AI (it won't cite it anymore)
- **Search & filter** — search by name, filter by category (Leave, Conduct, Benefits, Privacy, Work)
- **Stats dashboard** — shows total policies, indexed chunks, queries served, and accuracy rate

#### Tab 3 — Audit Log
A complete trail of everything that happens:

- Every AI response (which document was cited, which DB table was queried)
- Every file upload and deletion
- Hallucination blocks (if the AI tried to answer without a grounded source, it gets flagged)
- Who asked what, and when
- Can export the full log as CSV

---

## Quick Summary Table

| Feature | Employee | Admin |
|---|---|---|
| AI Chatbot | ✅ Personal data + policies | ✅ Org-wide data + policies |
| Upload/Delete policy files | ❌ | ✅ |
| View policy documents | Via chatbot citations | ✅ Full library access |
| Audit log | ❌ | ✅ |
| Data scope | Only their own records | Entire organization |
| Auto-audit logging | ❌ | ✅ Every query logged |

---

## Tech Highlights

- **Runs locally** — uses a local LLM (llama-3), no data leaves the company network
- **RAG (Retrieval-Augmented Generation)** — AI answers are grounded in actual uploaded documents, not made up
- **Hallucination filter** — answers are verified against the source before showing to the user
- **SOC 2 ready** — designed with compliance and audit trails in mind
