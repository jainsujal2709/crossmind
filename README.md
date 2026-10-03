# CrossMind — Netlify + Render Deployment

CrossMind is an AI/NLP-powered crossword learning web app. Users can upload PDF/PPTX/DOCX/XLSX/XLS/CSV/TXT files, paste notes, or enter a topic, choose Easy/Medium/Hard difficulty, generate a crossword, solve it, use hints, listen to clues, and review mistakes. It also includes normal-user and admin roles.

## Important deployment architecture

CrossMind is a Python/FastAPI application, but the production deployment is split into two services:

```text
Browser
   |
   v
Netlify
  Static frontend (HTML/CSS/JS)
   |
   | HTTPS API requests
   v
Render
  Python + FastAPI backend
   |
   v
Neon PostgreSQL
```

**Netlify hosts the frontend. Render hosts the Python backend. PostgreSQL stores users, documents, and crossword data.**

This split is intentional. Netlify's current framework/function documentation supports static HTML/CSS/JS and its documented Functions workflow, while Python/FastAPI is not a native Netlify web-service runtime. Render has a documented native FastAPI deployment flow. See the official docs linked at the end.

## What you need

Create accounts at:

1. GitHub — to store the project
2. Netlify — frontend hosting
3. Render — Python backend hosting
4. Neon — PostgreSQL database

You do **not** need to install Node.js for this version.

You do need Python 3.11+ for local backend development.

---

# PART A — Put the project on GitHub

## 1. Extract the ZIP

Extract `CrossMind.zip`.

The repository root must look like:

```text
CrossMind/
├── backend/
├── public/
├── data/
├── scripts/
├── tests/
├── requirements.txt
├── netlify.toml
├── render.yaml
├── .python-version
├── .env.example
└── README.md
```

Do not create another nested `CrossMind/CrossMind/` folder.

## 2. Create a GitHub repository

Create a new empty repository, for example:

```text
crossmind
```

Do not upload `.env`.

From the CrossMind folder:

```bash
git init
git add .
git commit -m "Initial CrossMind deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/crossmind.git
git push -u origin main
```

Replace `YOUR_USERNAME`.

---

# PART B — Create the PostgreSQL database

Use Neon for PostgreSQL.

1. Create a Neon project.
2. Create a database.
3. Copy its PostgreSQL connection string.

It will look similar to:

```text
postgresql://USER:PASSWORD@HOST/DATABASE?sslmode=require
```

Keep this value private.

---

# PART C — Deploy the Python backend to Render

## 1. Open Render

Create a new **Web Service** and connect the GitHub repository.

Render's FastAPI deployment uses a Python build command and an Uvicorn start command.

Use:

### Root Directory

```text
.
```

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Python version

Use:

```text
3.11.11
```

The repository already contains `.python-version`.

## 2. Add Render environment variables

In Render → Environment, add:

```text
DATABASE_URL=YOUR_NEON_POSTGRES_CONNECTION_STRING
```

```text
SECRET_KEY=GENERATE_A_LONG_RANDOM_SECRET
```

```text
ADMIN_EMAIL=your-admin-email@example.com
```

```text
ADMIN_PASSWORD=YOUR_STRONG_ADMIN_PASSWORD
```

```text
CORS_ORIGINS=https://YOUR-NETLIFY-SITE.netlify.app
```

At this point you may not know the final Netlify URL.

Temporarily use:

```text
CORS_ORIGINS=http://localhost:8000
```

Deploy the backend first.

## 3. Wait for deployment

Render should give you a URL similar to:

```text
https://crossmind-api.onrender.com
```

Copy it.

Test:

```text
https://crossmind-api.onrender.com/docs
```

You should see the FastAPI Swagger documentation.

If `/docs` loads, the Python backend is running.

---

# PART D — Create the Netlify frontend

## 1. Import the GitHub repository

Go to Netlify.

Choose:

```text
Add new project
→ Import an existing project
→ GitHub
```

Select your `crossmind` repository.

Netlify will read `netlify.toml`.

The important settings are:

```text
Build command:
bash scripts/netlify_build.sh

Publish directory:
dist
```

## 2. Add the backend URL

Before deploying, go to:

```text
Project configuration
→ Environment variables
```

Add:

```text
BACKEND_URL
```

Value:

```text
https://crossmind-api.onrender.com
```

Use YOUR actual Render URL.

Do not add `/api`.

Correct:

```text
https://crossmind-api.onrender.com
```

Incorrect:

```text
https://crossmind-api.onrender.com/api
```

## 3. Deploy

Click:

```text
Deploy
```

The build script will:

```text
public/
   ↓
dist/
   ↓
replace __BACKEND_URL__
   ↓
Netlify deployment
```

The browser will therefore call:

```text
https://crossmind-api.onrender.com/api/...
```

instead of trying to call the Netlify domain.

---

# PART E — IMPORTANT: Connect CORS

After Netlify gives you the final URL, for example:

```text
https://crossmind-ai.netlify.app
```

go back to Render:

```text
Environment
→ CORS_ORIGINS
```

Set:

```text
CORS_ORIGINS=https://crossmind-ai.netlify.app
```

Save and redeploy.

This allows the Netlify frontend to communicate with the FastAPI backend.

---

# PART F — Admin login

The admin account is created automatically when the backend starts if these variables are present:

```text
ADMIN_EMAIL
ADMIN_PASSWORD
```

Example:

```text
ADMIN_EMAIL=admin@crossmind.com
ADMIN_PASSWORD=Use-A-Strong-Password-Here
```

Open your Netlify site.

Login with the configured admin email/password.

Admins are redirected to:

```text
/admin.html
```

Normal users use:

```text
/app.html
```

Do not commit the admin password to GitHub.

---

# PART G — Local development

## Backend

Windows:

```bat
setup_windows.bat
```

Then edit `.env`.

Start:

```bat
run_windows.bat
```

Linux/macOS:

```bash
chmod +x setup_linux.sh
./setup_linux.sh
```

Edit `.env`.

Then:

```bash
chmod +x run_linux.sh
./run_linux.sh
```

Open:

```text
http://localhost:8000
```

API:

```text
http://localhost:8000/docs
```

---

# PART H — Local Netlify frontend

The normal local setup serves the frontend from FastAPI.

If you want to test the exact Netlify build locally:

```bash
export BACKEND_URL=http://localhost:8000
bash scripts/netlify_build.sh
```

This creates:

```text
dist/
```

You can then deploy `dist` as the frontend.

---

# PART I — Netlify deployment after code changes

Every time you change the code:

```bash
git add .
git commit -m "Update CrossMind"
git push
```

Netlify automatically rebuilds the frontend.

Render automatically redeploys the backend when its connected Git branch receives a new commit.

---

# PART J — Do NOT upload these

Never commit:

```text
.env
*.db
__pycache__/
.pytest_cache/
.venv/
venv/
```

The `.gitignore` already handles these.

---

# PART K — File responsibilities

## Frontend

```text
public/
```

Contains:

- Landing page
- Login/register
- User dashboard
- Crossword UI
- Admin UI
- CSS
- JavaScript

Netlify deploys this.

## Backend

```text
backend/
```

Contains:

- FastAPI
- Authentication
- Database
- NLP
- File parsing
- Crossword generation
- Scoring
- Admin APIs

Render runs this.

## Sample data

```text
data/sample_data/
```

Contains example learning material.

---

# PART L — Supported files

CrossMind currently accepts:

```text
PDF
PPTX
DOCX
XLSX
XLS
CSV
TXT
```

Legacy `.ppt` is not supported by the current parser. Save it as `.pptx` first.

---

# PART M — NLP pipeline

```text
Uploaded Material
       ↓
Document Parser
       ↓
Text Extraction
       ↓
Sentence Segmentation
       ↓
Stop-word Filtering
       ↓
Term Ranking
       ↓
Concept Detection
       ↓
Definition Detection
       ↓
Difficulty-based Clue Generation
       ↓
Answer Validation
       ↓
Crossword Generator
       ↓
Interactive Crossword
```

The current implementation uses local Python NLP logic and does not require a paid AI API.

---

# PART N — Voice

The browser's Web Speech API is used for voice input and speech synthesis.

Chrome/Edge generally provide the best browser support.

Voice input does not require a separate API key in the current implementation.

---

# PART O — Database

Production should use PostgreSQL.

Required:

```text
DATABASE_URL
```

SQLite is suitable for local testing.

Do not rely on a temporary server filesystem for production data.

---

# PART P — Troubleshooting

## Frontend says "Failed to fetch"

Check:

1. Render backend is running.
2. `BACKEND_URL` is correct in Netlify.
3. `CORS_ORIGINS` contains the exact Netlify URL.
4. Render has been redeployed after changing CORS.
5. Open the Render `/docs` URL directly.

## 401 error

Your JWT is invalid or expired.

Log out and log in again.

## Admin login doesn't work

Check:

```text
ADMIN_EMAIL
ADMIN_PASSWORD
```

in Render environment variables.

Then redeploy.

## Database error

Check:

```text
DATABASE_URL
```

and make sure the PostgreSQL connection string is valid.

## Upload error

The application currently limits uploads according to:

```text
MAX_UPLOAD_MB
```

The default is 4 MB.

Increase it carefully if your deployment provider permits larger request bodies.

## Crossword cannot be generated

Try:

- selecting more concepts
- reducing the clue count
- selecting Medium instead of Hard
- uploading/pasting more explanatory content

## `.ppt` doesn't work

Convert:

```text
.ppt → .pptx
```

and upload the `.pptx`.

---

# PART Q — Security checklist

Before making the project public:

- Change the admin password.
- Use a long random `SECRET_KEY`.
- Never commit `.env`.
- Use HTTPS URLs.
- Keep `DATABASE_URL` private.
- Keep admin credentials private.
- Keep CORS restricted to your Netlify domain.

---

# PART R — Production architecture

```text
                    ┌────────────────────┐
                    │       USER         │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │      NETLIFY       │
                    │                    │
                    │ HTML/CSS/JS        │
                    │ User UI            │
                    │ Admin UI           │
                    └─────────┬──────────┘
                              │ HTTPS
                              ▼
                    ┌────────────────────┐
                    │       RENDER       │
                    │                    │
                    │ Python             │
                    │ FastAPI            │
                    │ NLP                │
                    │ Crossword Engine   │
                    │ Authentication     │
                    └─────────┬──────────┘
                              │
                              ▼
                    ┌────────────────────┐
                    │       NEON         │
                    │    PostgreSQL      │
                    └────────────────────┘
```

# Official deployment documentation

Netlify deployment from GitHub:
https://docs.netlify.com/start/quickstarts/deploy-from-repository/

Netlify configuration:
https://docs.netlify.com/build/configure-builds/overview/

Netlify environment variables:
https://docs.netlify.com/build/environment-variables/get-started/

Render FastAPI:
https://render.com/docs/deploy-fastapi

Render environment variables:
https://render.com/docs/configure-environment-variables

---

# Final deployment checklist

Before opening the site to users:

[ ] GitHub repository created

[ ] Neon database created

[ ] Render backend deployed

[ ] Render `/docs` works

[ ] `DATABASE_URL` configured

[ ] `SECRET_KEY` configured

[ ] `ADMIN_EMAIL` configured

[ ] `ADMIN_PASSWORD` configured

[ ] Netlify site created

[ ] `BACKEND_URL` configured in Netlify

[ ] Netlify deployment successful

[ ] `CORS_ORIGINS` changed to final Netlify URL

[ ] Normal registration tested

[ ] Normal login tested

[ ] Admin login tested

[ ] PDF upload tested

[ ] PPTX upload tested

[ ] Text input tested

[ ] Topic mode tested

[ ] Easy crossword tested

[ ] Medium crossword tested

[ ] Hard crossword tested

[ ] Crossword submission tested

[ ] Hints tested

[ ] Voice tested

[ ] Admin dashboard tested

[ ] Database persistence tested

---

## The only manual configuration required

You cannot eliminate the creation of third-party hosting/database accounts from the source code itself.

Once the accounts exist, the deployment requires only these external values:

```text
Render:
DATABASE_URL
ADMIN_EMAIL
ADMIN_PASSWORD
CORS_ORIGINS

Netlify:
BACKEND_URL
```

Everything else is included in this repository.
