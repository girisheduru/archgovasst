# AI Architecture Governance Assistant

[![Current architecture of the AI Architecture Governance Assistant](docs/images/architecture-current.png)](docs/images/architecture-current.png)

Select the diagram to open the full-resolution image.

The review runs through six LangGraph nodes with two human decisions. Chroma stores versioned standards. Live review state resides in backend memory until a restart. Evaluation runs separately against an exported report and a human answer key.

## Rule selection and evidence retrieval

`prepare` loads the latest effective version of every applicable rule. Applicability comes from the selected document type and standards date. `extract` ranks passages **from the uploaded design** for each of those rules using keyword overlap and OpenAI embeddings.

```mermaid
flowchart TD
    Chroma["Chroma versioned standards"] --> Prepare["Prepare every applicable rule"]
    Design["Parsed PDF pages or Word body blocks"] --> Passages["Build passages with original source labels"]
    Prepare --> Rank["Rank design passages for each rule"]
    Passages --> Rank
    Rank --> Extract["Extract quotes from the highest-ranked passages"]
    Extract --> Verify["Verify quotes against the supplied source text"]
    Verify -->|"Rules with verified quotes"| Confirm["Reviewer confirms evidence for all rules"]
    Verify -->|"Rules without a verified quote"| Full["Search the full design"]
    Full --> Final["Verify quotes and identify evidence gaps"]
    Final --> Confirm
    Confirm -->|"Confirmed"| Assess["Calculate findings and risk, then request report approval"]
```

Passage text and embeddings are used during extraction. Chroma continues to store the approved standards. For short designs and when passage ranking is unavailable, extraction searches the full design directly. Every applicable rule reaches the reviewer with either a verified citation or an evidence gap. See the [workflow diagrams](flowdiagrams.md#document-review) and [baseline comparison procedure](backend/README.md#compare-retrieval-with-the-full-document-baseline).
