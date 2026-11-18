# Project command reference

Run commands in the root of the `archgovasst` clone unless a section gives a different location. The React app lives in `frontend/`. Its Vite version supports Node.js 20.19+ on the 20.x line, or 22.12 and newer.

## Set up and run the frontend

| Command | What it does |
| --- | --- |
| `node -v` | Shows the installed Node.js version. |
| `npm -v` | Shows the installed npm version. |
| `npm --prefix frontend ci` | Installs the exact versions in `frontend/package-lock.json`. Run this after cloning. |
| `npm --prefix frontend run dev` | Starts the Vite development server. Open the local URL it prints. |
| `npm --prefix frontend run build` | Builds the production frontend into `frontend/dist/`. |
| `npm --prefix frontend run preview` | Serves the production build locally. Build first. |

The original Hello World app lived at the repository root. At that stage, `npm install` installed dependencies and created the lockfile, `npm run dev` started the app, and `npm run build` built it. With the current layout, run those scripts inside `frontend/` or use the root-level commands above.

## Set up and run the backend

Run these commands from the clone root with Python 3.11 or newer. The setup commands only need to run once per environment.

| Command | What it does |
| --- | --- |
| `python3 -m venv .venv` | Creates an isolated Python environment. |
| `.venv/bin/python -m pip install -r backend/requirements.txt` | Installs the backend dependencies. |
| `.venv/bin/python -m uvicorn backend.main:app --reload` | Starts the FastAPI development server on port 8000. |
| `curl http://127.0.0.1:8000/api/reviews/sample` | Fetches a fictional architecture review with randomized findings and next steps. Run from another terminal while the server is running. |

Open [the interactive API docs](http://127.0.0.1:8000/docs) while the server is running.

## Verify review tracing

From the clone root, run `.venv/bin/python -m unittest discover -s backend/tests -v` after installing the backend dependencies and `httpx` (used by FastAPI's test client). This checks the trace hierarchy through the API and the real LangGraph, checkpoint resumes, session grouping, error status, and disabled tracing. OpenAI and Chroma are mocked, and spans are collected in memory.

## Import standards and evaluate a review

From the clone root, install the backend dependencies and configure Chroma before running these commands. Import and optional judging also require `OPENAI_API_KEY` in the shell environment. See the [backend guide](backend/README.md) for file formats.

| Command | What it does |
| --- | --- |
| `.venv/bin/python -m backend.governance.standards backend/standards/STD-*.docx` | Imports 26 rules from the bundled Word standards into Chroma and overwrites records with matching rule IDs and effective dates. Requires backend dependencies, an OpenAI API key, and a Chroma connection. |
| `.venv/bin/python -m backend.governance.evaluate /path/to/review.json /path/to/design.pdf /path/to/answer-key.json` | Scores an exported report against its source document and human answer key. Append `--judge` for OpenAI scoring. |

## Run the sample review backend

Run these commands from the clone root. The backend uses Python 3.11 in the local setup. Use a second terminal for the Vite development server.

| Command | What it does |
| --- | --- |
| `python3 -m venv .venv` | Creates the Python virtual environment if it does not already exist. |
| `.venv/bin/python -m pip install -r backend/requirements.txt` | Installs the backend dependencies into that environment. |
| `.venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000` | Starts the FastAPI backend on the port expected by the Vite proxy. |
| `curl -fsS http://127.0.0.1:8000/api/reviews/sample` | Checks the backend directly and prints a fictional sample review as JSON. |

If the direct backend check returns JSON but the frontend request returns HTML, restart Vite so it loads `frontend/vite.config.js`. From the clone root, `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174 --strictPort` starts a fresh frontend on port 5174 while leaving the process on port 5173 running. Run `curl -i http://127.0.0.1:5174/api/reviews/sample` to verify that the frontend serves the API response as JSON.

## Connect the frontend to Railway

If Railway reports that `/backend` only contains `.gitkeep`, check that its source branch on GitHub includes the FastAPI files. From the clone root, run these commands when deploying from `main`:

| Command | What it does |
| --- | --- |
| `git add -- backend/main.py backend/governance backend/requirements.txt` | Stages the FastAPI entry point, application package, and dependencies. |
| `git commit -m 'Add FastAPI backend' -- backend/main.py backend/governance backend/requirements.txt` | Commits the backend runtime files. |
| `git push origin main` | Publishes the commit to the GitHub branch connected to Railway. |

1. Configure the Railway backend service with `/backend` as its root directory. Set the start command to `uvicorn main:app --host 0.0.0.0 --port "$PORT"`. Railway provides `PORT`. Generate a public HTTPS domain under Networking.
2. Set `CORS_ALLOWED_ORIGINS` in the Railway backend service's Variables tab. Use the origin shown in the browser, such as `https://your-frontend.example.com` or `http://localhost:5173`. For multiple origins, separate them with commas. Redeploy the backend after changing it.
3. Set `VITE_API_BASE_URL` in the frontend build environment to the Railway backend URL, such as `https://your-backend.up.railway.app`. Include `https://` and leave off the `/api` path. If the frontend is hosted on Railway, set this in the frontend service's Variables tab. Rebuild the frontend after changing it.
4. To run the frontend locally against Railway, use `frontend/.env.example` as a template for `frontend/.env.local`. Set `VITE_API_BASE_URL` and restart the Vite server. Add the exact local frontend origin to Railway's `CORS_ALLOWED_ORIGINS`.

If `VITE_API_BASE_URL` is empty, the frontend uses the existing local Vite proxy. Vite includes `VITE_` variables in the browser bundle, so use them only for public values.

## Clone and check GitHub access

| Command | What it does |
| --- | --- |
| `git clone https://github.com/girisheduru/archgovasst.git archgovasst` | Clones the active GitHub repository into an `archgovasst` subfolder. Run from the directory where you want the clone. |
| `cd archgovasst` | Enters the clone from its parent directory. |
| `gh auth status` | Shows the GitHub CLI authentication status. |
| `gh api user --jq .login` | Shows the GitHub login used by the CLI. |
| `gh repo view girisheduru/archgovasst --json nameWithOwner,visibility,defaultBranchRef,viewerPermission` | Shows the repository name, visibility, default branch, and your access level. |
| `git remote -v` | Lists the fetch and push URLs for each remote. |
| `git ls-remote --symref origin HEAD 'refs/heads/*'` | Checks the remote's default branch and lists its branch heads. |
| `git fetch --prune origin` | Fetches remote updates and removes stale remote-tracking references. |
| `git remote set-head origin -a` | Sets the local `origin/HEAD` reference to match the remote's default branch. |

## Review, commit, and push changes

| Command | What it does |
| --- | --- |
| `git status --short --branch` | Shows the current branch, its upstream status, and local changes. |
| `git diff --stat` | Summarizes unstaged changes by file. |
| `git diff --check` | Checks unstaged changes for whitespace errors. |
| `git add -- frontend/index.html frontend/src/main.jsx frontend/src/style.css` | Stages the three files changed for the landing page. Adjust paths for other changes. |
| `git diff --cached --check` | Checks staged changes for whitespace errors. |
| `git commit -m 'Add architecture governance landing page'` | Records the staged changes locally. Use a message that describes the change. |
| `git push origin main` | Pushes local commits on `main` to `archgovasst` on GitHub. |

From the parent directory, `git -C archgovasst status --short --branch` and `git -C archgovasst push origin main` run the same operations inside the clone.

## Earlier repository setup

These commands record the original setup and subsequent switch. Use the clone and workflow above for current work.

| Command | What it did |
| --- | --- |
| `git init -b main` | Requested a new working repository with `main` as its initial branch. The workspace already had Git metadata, so its existing `master` branch was retained. |
| `gh repo create girisheduru/AIArchGovAsst --private --source=. --remote=origin --push` | Created the earlier private GitHub repo, configured `origin`, and pushed the initial React app. |
| `mkdir frontend backend` | Created the frontend and backend directories during the initial reorganization. |
| `mv index.html package.json package-lock.json src node_modules dist frontend/` | Moved the app and its existing local build and dependencies into `frontend/`. |
| `touch backend/.gitkeep` | Added a placeholder so Git could track the empty backend directory. |
| `git push origin master` | Published the folder reorganization to the earlier repository. |
| `git remote set-url origin https://github.com/girisheduru/archgovasst.git` | Repointed the parent workspace's remote to the new repository before creating the separate clone. |
| `git branch --unset-upstream master` | Cleared the parent workspace's tracking configuration for the old `master` upstream. |

## Keeping this reference current

When sharing a new project command, add it here with its purpose, working directory, and any required setup. Update an existing entry when the workflow changes.
