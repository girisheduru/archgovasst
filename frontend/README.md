# Architecture Governance Assistant Frontend

The React and Vite app presents the upload and review panels. The [FastAPI backend](../backend/README.md) runs LangGraph, reads the Chroma standards, and makes the OpenAI calls.

1. Upload a text-based PDF or Word document and select its type and declared risk tier. The optional standards date selects effective rule versions.
2. Compare the extracted quotes with the required evidence. Enter your reviewer name to confirm or reject the extraction.
3. Review the assessed risk tier and cited findings, then approve or reject the report.
4. Download the JSON decision record to keep a copy. Refreshing the same tab restores the review while the backend process is running. After a backend restart, upload the document to start a new review.

Select **Load sample review** to try fictional findings without an OpenAI key or Chroma.

## Code layout

- [`main.jsx`](src/main.jsx) renders the page and mounts the review components.
- [`DocumentReview.jsx`](src/components/DocumentReview.jsx) manages review state and coordinates the [upload panel](src/components/UploadPanel.jsx) and [review panel](src/components/ReviewPanel.jsx).
- [`api/reviews.js`](src/api/reviews.js) handles document review requests and API errors.
- [`SampleReview.jsx`](src/components/SampleReview.jsx) renders the separate fictional sample.

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

## Build and preview

From the repository root, run the following commands. The build writes to `frontend/dist/`, and the preview command serves that build locally.

```sh
npm --prefix frontend run build
npm --prefix frontend run preview
```

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
