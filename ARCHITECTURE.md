# AI Architecture Governance Assistant

[![Current architecture of the AI Architecture Governance Assistant](docs/images/architecture-current.png)](docs/images/architecture-current.png)

Select the diagram to open the full-resolution image.

The review runs through six LangGraph nodes with two human decisions. Chroma stores versioned standards. Live review state resides in backend memory until a restart. The image shows single-report evaluation. The [Arize AX benchmark workflow](flowdiagrams.md#arize-ax-benchmark) uses the bundled designs, standards, and answer workbook to evaluate extraction and gap assessment in batches.

The [performance reporting workflow](flowdiagrams.md#performance-dashboard) connects the benchmark and application checks to the separate `/performance` page. At startup, FastAPI publishes the full benchmark dataset and templates to Arize AX in the background when configured. Token-authorized actions can run the benchmark, publish assets, run backend tests in a separate Python process, or validate fixtures. FastAPI reads the latest summaries from disk as the page polls for progress.

## Diagram colors

| Color | Meaning |
| --- | --- |
| Blue | People, uploads, and browser interactions |
| Green | API and deterministic processing |
| Purple | OpenAI calls and LLM evidence extraction |
| Orange | Standards storage and saved review state |
| Amber | Validation branches and human decisions |
| Teal | Results and completed steps |
| Red | Rejection |
| Gray | Optional integrations and workflow boundaries |

Node labels and arrow labels also identify each step and decision.

## RAG upload

Approved Word standards enter through the token-protected upload API or the CLI. The import extracts and validates rules, generates OpenAI embeddings, and stores each rule version in Chroma. A matching rule ID and effective date overwrites that version.

```mermaid
flowchart TD
    Web["Select Word standards and display all filenames at /standards"] --> Auth["Check the import token"]
    CLI["Run the standards import CLI with Word files"] --> Parse["Extract rule IDs, effective dates, statements, and evidence guidance"]
    Auth --> Parse
    Parse --> Duplicate{"Duplicate rule ID and effective date in the import?"}
    Duplicate -->|"Yes"| Reject["Reject the import"]
    Duplicate -->|"No"| Lookup["Look up existing rule versions in Chroma"]
    Lookup --> Embed["Generate embeddings with OpenAI"]
    Embed --> Save["Write records keyed by rule ID and effective date"]
    Save --> Result["Return counts of versions added and overwritten"]

    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Web,CLI user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Auth,Parse process;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class Duplicate decision;
    classDef rejected fill:#fee2e2,stroke:#dc2626,color:#7f1d1d,stroke-width:2px;
    class Reject rejected;
    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Lookup,Save store;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class Embed llm;
    classDef output fill:#ccfbf1,stroke:#0f766e,color:#134e4a,stroke-width:2px;
    class Result output;
```

Standards maintainers can also clear the configured Chroma standards collection from `/standards`. The browser asks for confirmation and the backend validates the import token before deleting the rule versions and their embeddings. The next import recreates the collection. See the [reset workflow](flowdiagrams.md#rag-database-reset).

## Rule selection and evidence retrieval

### Review flow

`retrieve_applicable_rules` retrieves the latest effective version of every applicable rule from Chroma using the selected document type and standards date. `extract_evidence_with_llm` ranks passages **from the uploaded design** using keyword overlap and OpenAI embeddings, asks the LLM for supporting quotes, and verifies each quote against its cited source.

```mermaid
flowchart TD
    Chroma["Chroma versioned standards"] --> Prepare["Retrieve every applicable rule"]
    Design["Parsed PDF pages or Word body blocks"] --> Passages["Build passages with original source labels"]
    Prepare --> Rank["Rank design passages for each rule"]
    Passages --> Rank
    Rank --> Extract["Extract quotes with an LLM from the highest-ranked passages"]
    Extract --> Verify["Verify quotes against the supplied source text"]
    Verify -->|"Rules with verified quotes"| Confirm["Reviewer confirms evidence for all rules"]
    Verify -->|"Rules without a verified quote"| Full["Search the full design"]
    Full --> Final["Verify quotes and identify evidence gaps"]
    Final --> Confirm
    Confirm -->|"Confirmed"| Assess["Calculate findings and risk, then request report approval"]

    classDef store fill:#ffedd5,stroke:#c2410c,color:#7c2d12,stroke-width:2px;
    class Chroma,Prepare store;
    classDef user fill:#dbeafe,stroke:#2563eb,color:#172554,stroke-width:2px;
    class Design user;
    classDef process fill:#dcfce7,stroke:#15803d,color:#14532d,stroke-width:2px;
    class Passages,Rank,Verify,Final,Assess process;
    classDef llm fill:#ede9fe,stroke:#7c3aed,color:#3b0764,stroke-width:2px;
    class Extract,Full llm;
    classDef decision fill:#fef3c7,stroke:#a16207,color:#713f12,stroke-width:2px;
    class Confirm decision;
```

Passage text and embeddings are used during extraction. Chroma continues to store the approved standards. For short designs and when passage ranking is unavailable, extraction searches the full design directly. Every applicable rule reaches the reviewer with either a verified citation or an evidence gap. See the [workflow diagrams](flowdiagrams.md#document-review) and [baseline comparison procedure](backend/README.md#compare-retrieval-with-the-full-document-baseline).

The review API provides two on-demand actions for rules with evidence gaps. **Suggest next step** uses the approved rule and relevant design passages to draft guidance. **Recheck with a supporting document** searches the uploaded file for that rule alone while evidence confirmation is pending. FastAPI stages a verified candidate in the checkpoint state. `confirm_evidence` includes the candidate only when the reviewer selects its quote and confirms the evidence. The policy node then calculates gaps and risk using the confirmed evidence.
