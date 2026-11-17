# Architecture Governance Assistant Frontend

The React and Vite app presents the upload and review panels. The [FastAPI backend](../backend/README.md) runs LangGraph, reads the Chroma standards, and makes the OpenAI calls.

Select **Start a document review** on the homepage or **Document review** in the header to open `/review`. You can bookmark or refresh that page directly.

1. Upload a text-based PDF or Word document and select its type and declared risk tier. The optional standards date selects effective rule versions.
2. Use **Standards comparison** to see the rule text, source standard, and effective date alongside evidence from the design. The page counts rules with evidence and flags missing evidence. Enter your reviewer name to confirm or reject the extraction.
3. Review the assessed risk tier and cited findings, then approve or reject the report.
4. Download the JSON decision record to keep a copy. Refreshing the same tab restores the review while the backend process is running. After a backend restart, upload the document to start a new review.

## Code layout

- [`main.jsx`](src/main.jsx) selects the homepage or the dedicated document review page based on the URL.
- [`DocumentReview.jsx`](src/components/DocumentReview.jsx) manages review state and coordinates the [upload panel](src/components/UploadPanel.jsx) and [review panel](src/components/ReviewPanel.jsx).
- [`api/reviews.js`](src/api/reviews.js) handles document review requests and API errors.
- [`StandardsUpload.jsx`](src/components/StandardsUpload.jsx) submits approved Word standards from `/standards`.

## Upload standards

Select **Upload standards** on the homepage or **Standards** in the header. Select the approved Word (.docx) standards, then enter the import token configured on the backend. Use the [bundled standards format](../backend/standards/README.md). The form shows how many rule versions were added and how many were already present. The backend extracts rule statements and evidence guidance from the documents and sends that text to OpenAI for embedding. It stores the rule records in Chroma.

## Run locally

Use Node.js 20.19 or later on the 20.x line, or Node.js 22.12 or later. From the repository root, run the following commands and open the URL Vite prints.

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Start the backend on port 8000. Configure the OpenAI key and import approved standards on the backend to enable document reviews. By default, the Vite development server forwards `/api` requests to `http://127.0.0.1:8000`.

## Connect to a hosted backend

Use [`.env.example`](.env.example) as a template for `frontend/.env.local` during local development. Set `VITE_API_BASE_URL` to the backend's public HTTPS origin, omitting `/api`, and restart Vite. The backend must allow the browser's exact frontend origin in `CORS_ALLOWED_ORIGINS`.

For a hosted frontend, set `VITE_API_BASE_URL` in the build environment before building. Vite includes this value in the browser bundle, so use a public URL. If you leave it blank, the app makes same-origin requests and your hosting setup needs to route `/api` to the backend.

On Vercel, set the project root directory to `frontend` so [`vercel.json`](vercel.json) routes direct visits to `/review` and `/standards` to the app. On other static hosts, serve `index.html` for both paths.

## Build and preview

From the repository root, run the following commands. The build writes to `frontend/dist/`, and the preview command serves that build locally.

```sh
npm --prefix frontend run build
npm --prefix frontend run preview
```

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
