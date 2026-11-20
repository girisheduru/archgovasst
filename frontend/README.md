# Architecture Governance Assistant Frontend

The React and Vite app presents the upload and review panels. The [FastAPI backend](../backend/README.md) runs LangGraph, reads the Chroma standards, and makes the OpenAI calls.

The homepage introduces **AI Architecture Governance Assistant** through the problems of scattered policies, unclear applicability, manual document reviews, and inconsistent coverage. It highlights encryption, identity, networking, secrets, observability, and resiliency as topics to document for review against the imported standards.

Select **Start a document review** on the homepage or **Document review** in the header to open `/review`. You can bookmark or refresh that page directly.

The **Review progress** banner shows all four stages and identifies the current checkpoint. The progress indicators use green for completed stages and passed checkpoints, blue for the current stage, purple for the next stage, red for rejection, and gray for stages that are upcoming or were skipped. Decision buttons and recorded outcomes use green for approval and red for rejection.

1. Upload a text-based PDF or Word document and select its type and declared risk tier. The optional standards date selects effective rule versions. The review searches relevant design passages for every applicable rule and checks the full design for rules without a verified quote.
2. Browse **Standards comparison** with all rules visible by default. The **Evidence status** options and their counts are always visible. Use them with the adjacent **Standard** filter to narrow the list. Expand any finding to see the rule text, effective date, and design evidence. Enter your name in **Record decision** to confirm or reject the extraction. The form is always expanded and stays at the top of the viewport while you scroll on larger screens.
3. Select **?** beside **Standards comparison** for help interpreting the evidence badges and their effect on the assessed risk tier. Evidence gaps show a risk badge alongside **Not evidenced**, with green for low risk, orange for medium risk, and red for high risk. Use **Record decision** to approve or reject the report.
4. At either checkpoint, expand a finding and select **Add comment** to give feedback on that rule. Draft comments save with your decision, including comments on findings hidden by the filters. Use **Decision note** for the overall rationale. Expand **Decision history** beside **Record decision** on larger screens to see earlier decisions and notes. On smaller screens it sits below the form, and after the review ends it appears above **Standards comparison**.
5. After the report is approved or rejected, select **Download final report (PDF)** to save the outcome, risk tiers, standards comparison, finding comments, and reviewer decisions. **Download decision record** saves the JSON used for evaluation, including comments in the decision history. Refreshing the same tab restores the review while the backend process is running. After a backend restart, upload the document to start a new review.

### Work on an evidence gap

Expand a **Not evidenced** finding and select **Suggest next step** for AI-generated guidance on what to clarify and what evidence to provide. Before confirming evidence, you can also select **Recheck with a supporting document**, choose a text-based PDF or Word file, and select **Recheck this rule**. If a verified quote appears, read it and select **Include this quote when I confirm evidence** to accept it with your evidence decision. Unchecked quotes leave the gap open. Included quotes cite the supporting filename and source location in the review and final report.

## View AI system performance

Select **Performance** in the header to open `/performance`. Overview tiles show the latest design, prompt, and test counts. The AI benchmark tiles show quality scores when a run completes, alongside model, retrieval mode, and per-design results. The **Arize AX assets** panel shows startup publication progress, the space, dataset, Prompt Hub versions, and latest experiment.

During a benchmark, the page shows the number of designs reviewed and the separate experiment upload step. If Arize rejects the upload, the scored results stay visible and the action panel reports the failure.

The AI benchmark counts a design as passed when its evidence gap set and assessed risk tier both match the answer key. The per-design table shows which designs passed. The application tests panel counts successful checks and distinct failed checks, with skips reported separately.

Select **Run AI benchmark**, **Publish Arize assets**, **Run application tests**, or **Validate benchmark fixtures**. The page prompts for the configured performance run token if the field is empty. Use **Benchmark scope** to choose one design or the full benchmark. The page refreshes automatically while an action runs. If a button is unavailable, its requirements appear below it or in the action panel. Expand **Backend configuration** to see which settings the connected FastAPI backend received. Select **Refresh results** after a terminal or CI run. [Backend reporting setup](../backend/README.md#performance-dashboard)

## Code layout

- [`main.jsx`](src/main.jsx) selects the page based on the URL.
- [`DocumentReview.jsx`](src/components/DocumentReview.jsx) manages review state and coordinates the [upload panel](src/components/UploadPanel.jsx) and [review panel](src/components/ReviewPanel.jsx).
- [`api/reviews.js`](src/api/reviews.js) handles document review requests and API errors.
- [`StandardsUpload.jsx`](src/components/StandardsUpload.jsx) imports approved Word standards and clears the RAG database from `/standards`.
- [`PerformanceDashboard.jsx`](src/components/PerformanceDashboard.jsx) displays saved benchmark and test summaries from `/api/performance`.

## Upload standards

Select **Upload standards** on the homepage or **Standards** in the header. Select the approved Word (.docx) standards, then enter the import token configured on the backend. The form lists every selected file and, after a successful import, shows the imported filenames and the counts of rule versions added and overwritten. The backend extracts rule statements and evidence guidance from the documents and sends that text to OpenAI for embedding. Use the [bundled standards format](../backend/datadocs/README.md).

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

On Vercel, set the project root directory to `frontend` so [`vercel.json`](vercel.json) routes direct visits to `/review`, `/standards`, and `/performance` to the app. On other static hosts, serve `index.html` for these paths.

## Build and preview

From the repository root, run the following commands. The build writes to `frontend/dist/`, and the preview command serves that build locally.

```sh
npm --prefix frontend run build
npm --prefix frontend run preview
```

See [COMMANDS.md](../COMMANDS.md) for the project command reference.
