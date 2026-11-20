# Prompts used in the application

[prompts_used.csv](prompts_used.csv) lists one row per distinct LLM instruction string. The `prompt_text` column contains the exact text passed to OpenAI, with composed prompts expanded. The application sends the instructions and a separate JSON input to the OpenAI Responses API and parses the result with a Pydantic schema. The input field names below describe what is supplied at runtime. [OpenAI provider](backend/governance/providers/openai.py#L19-L37)

## EVIDENCE_EXTRACTION

Finds up to one exact, contiguous quote per rule, with its original source label. The prompt tells the model to treat document text as data and omit rules whose evidence is missing, incomplete, negated, or merely aspirational.

- **Initial review.** Searches the full extracted design text for rules still unresolved after passage extraction. It also handles reviews that skip passage extraction, including designs with at most three passages and reviews run with `EVIDENCE_RETRIEVAL_MODE=full_document`. [Initial review call](backend/governance/agent/evidence.py#L120-L142)
- **Supporting-document recheck.** Searches a newly uploaded supporting document for one rule with an evidence gap. A matching quote becomes a candidate the reviewer can select at the evidence checkpoint. [Recheck call](backend/governance/agent/evidence.py#L111-L117), [Review endpoint](backend/governance/api/document_reviews.py#L142-L181), [Evidence checkpoint](backend/governance/agent/graph.py#L26-L39)
- **Input and output.** Takes `rules` (each with `id`, `rule_text`, and `evidence_required`) and `document` (source labels mapped to extracted text). Returns `evidence` entries with `rule_id`, `source`, and `quote`. The backend normalizes the quote's whitespace and checks that the quote appears under the returned source label in the text allowed for that rule. [Prompt definition](backend/governance/agent/prompts.py#L1-L7), [Schema and verification](backend/governance/agent/evidence.py#L20-L61)

## PASSAGE_EXTRACTION

Extends `EVIDENCE_EXTRACTION` with instructions to use only the passages assigned to each rule. The model must cite the original source label and copy the quote from a single passage. It omits a rule if those passages provide insufficient context. [Prompt definition](backend/governance/agent/prompts.py#L9-L13)

- **When it runs.** During an initial review with more than three design passages, unless full-document mode is enabled. The backend ranks up to three passages per rule and calls the model only when ranking selects at least one passage. Evidence that is still unresolved proceeds to the full-document search. [Passage extraction and fallback](backend/governance/agent/evidence.py#L64-L87), [Initial review call](backend/governance/agent/evidence.py#L120-L142)
- **Input and output.** Takes `rules` with the standard rule fields plus `passage_ids`, and `passages` mapping IDs to source-label/text maps. Returns the same `evidence` structure as `EVIDENCE_EXTRACTION`. Quote verification is limited to the passages assigned to each rule. [Payload and allowed passages](backend/governance/agent/evidence.py#L43-L87)

## GAP_GUIDANCE

Drafts two short plain-text fields for a rule with an evidence gap. It explains what still needs to be demonstrated and suggests a concrete artifact or design detail the owner can provide. It uses the approved rule's evidence requirements and asks the model to describe uncertainty when passages are absent or inconclusive. [Prompt definition](backend/governance/agent/prompts.py#L15-L24)

- **When it runs.** When a reviewer clicks **Suggest next step** for a rule with no verified evidence in the review. [Review action](frontend/src/components/EvidenceGapActions.jsx#L33-L45), [Gap endpoint](backend/governance/api/document_reviews.py#L131-L139)
- **Input and output.** Takes one `rule` and `design_passages`. It uses all passages when there are at most three, up to three ranked passages for longer designs, or an empty list if ranking fails. Returns `missing_evidence` and `next_step`. The endpoint returns these fields directly to the reviewer. [Schema and inputs](backend/governance/agent/evidence.py#L30-L40), [Guidance call](backend/governance/agent/evidence.py#L90-L108)

## JUDGE_INSTRUCTIONS

Evaluates an exported review against the source text and a human answer key. It scores clarity and actionability from 1 (poor) to 5 (strong) and hallucination risk from 1 (low) to 5 (high), then briefly explains the scores. [Prompt definition and schema](backend/governance/evaluation/judge.py#L12-L23)

- **When it runs.** The evaluation CLI calls the judge when `--judge` is enabled and includes its result under `llm_judge` in the evaluation output. [Evaluation CLI](backend/governance/evaluate.py#L15-L35)
- **Input and output.** Takes the exported `findings` and `risk_tier`, the `answer_key`, the extracted `source` sections, and optional `supporting_documents_by_sha256`. Returns `clarity`, `actionability`, `hallucination_risk`, and `rationale`. [Judge call](backend/governance/evaluation/judge.py#L26-L43)

## Embedding inputs

The application also sends two text formats to OpenAI's embeddings API to generate vectors. These requests supply text directly and have no instruction string.

- **Standards import.** Sends each rule's quote followed by a newline and its evidence requirement. The resulting vector is stored with the rule version in Chroma. [Standards ingestion](backend/governance/standards_store/ingestion.py#L31-L48)
- **Design passage ranking.** Sends each passage's section texts joined by newlines. In the same batch it sends each rule's quote followed by a newline and its evidence requirement. The ranking code combines semantic and keyword scores before selecting passages. [Passage ranking](backend/governance/agent/retrieval.py#L51-L75)
