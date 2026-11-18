# Architecture Governance Assistant Frontend

The React and Vite app presents the upload and review panels. The [FastAPI backend](../backend/README.md) runs LangGraph, reads the Chroma standards, and makes the OpenAI calls.

The homepage introduces **AI Architecture Governance Assistant** through the problems of scattered policies, unclear applicability, manual document reviews, and inconsistent coverage. It highlights encryption, identity, networking, secrets, observability, and resiliency as topics to document for review against the imported standards.

Select **Start a document review** on the homepage or **Document review** in the header to open `/review`. You can bookmark or refresh that page directly.

**Review progress** shows all four stages throughout the review. The progress indicators use green for completed stages and passed checkpoints, blue for the current stage, purple for the next stage, red for rejection, and gray for stages that are upcoming or were skipped. Decision buttons and recorded outcomes use green for approval and red for rejection.

1. Upload a text-based PDF or Word document and select its type and declared risk tier. The optional standards date selects effective rule versions. The review searches relevant design passages for every applicable rule and checks the full design for rules without a verified quote.
2. Browse **Standards comparison** with all rules visible by default. The **Evidence status** options and their counts are always visible. Use them with the adjacent **Standard** filter to narrow the list. Expand any finding to see the rule text, effective date, and design evidence. Open **Record decision**, which stays at the top of the viewport while you scroll through the findings, and enter your name to confirm or reject the extraction.
3. Review the assessed risk tier and cited findings, then use **Record decision** to approve or reject the report. Evidence gaps show a risk badge alongside **Not evidenced**, with green for low risk, orange for medium risk, and red for high risk. Expand **How to read design evidence** for an explanation of the evidence badges and their effect on the assessed risk tier.
4. At either checkpoint, expand a finding and select **Add comment** to give feedback on that rule. Draft comments save with your decision, including comments on findings hidden by the filters. Use **Decision note** for the overall rationale. Expand **Decision history** above the findings to see earlier decisions and notes. It sits beside **How to read design evidence** when both are available and there is room.
5. After the report is approved or rejected, select **Download final report (PDF)** to save the outcome, risk tiers, standards comparison, finding comments, and reviewer decisions. **Download decision record** saves the JSON used for evaluation, including comments in the decision history. Refreshing the same tab restores the review while the backend process is running. After a backend restart, upload the document to start a new review.

## Code layout

- [`main.jsx`](src/main.jsx) selects the homepage or the dedicated document review page based on the URL.
- [`DocumentReview.jsx`](src/components/DocumentReview.jsx) manages review state and coordinates the [upload panel](src/components/UploadPanel.jsx) and [review panel](src/components/ReviewPanel.jsx).
- [`api/reviews.js`](src/api/reviews.js) handles document review requests and API errors.
- [`StandardsUpload.jsx`](src/components/StandardsUpload.jsx) imports approved Word standards and clears the RAG database from `/standards`.

## Upload standards

Select **Upload standards** on the homepage or **Standards** in the header. Select the approved Word (.docx) standards, then enter the import token configured on the backend. The form lists every selected file and, after a successful import, shows the imported filenames and the counts of rule versions added and overwritten. The backend extracts rule statements and evidence guidance from the documents and sends that text to OpenAI for embedding. Use the [bundled standards format](../backend/standards/README.md).

If the form says OpenAI rejected the backend credentials, have the backend administrator check `OPENAI_API_KEY` before retrying. See the [backend setup guide](../backend/README.md#upload-approved-standards-from-the-frontend).

Chroma overwrites a stored rule when the uploaded rule has the same ID and **Effective date**. Include each rule version once per upload.

To delete all stored standards and their embeddings, enter the same token, select **Clear RAG database**, and confirm the deletion. The page reports whether the collection was cleared or already empty. Import approved standards again before starting a new document review.

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
