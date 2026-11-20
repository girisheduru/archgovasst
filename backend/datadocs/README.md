# Governance standards and evaluation data

- [`standards/`](standards/) contains the four versioned Word standards used by the live import and the benchmark.
- [`solution-designs/`](solution-designs/) contains the 24 sample Word designs.
- [`Answer_Key.xlsx`](Answer_Key.xlsx) links designs to expected findings by document ID and references the matching rules. See the [Arize AX benchmark guide](../README.md#run-the-arize-ax-benchmark).

The four Word standards contain 26 rules. Use their layout for new documents.

- Put `Document ID` (for example, `STD-01`) and `Effective date` (`YYYY-MM-DD`) in the metadata table, with each value in the cell to the right of its label.
- List the rules between the `3. Rules` and `4. Exceptions` headings. Give each rule three consecutive paragraphs with an ID and title (for example, `ARC-01 Scalability`), the rule statement, and the evidence guidance beginning with `Evidence expected in the design document:`.
- Keep each rule ID unique across standards and reuse it when publishing a new version with a later effective date.

Every imported rule applies to solution design and architecture decision reviews. Missing evidence defaults to medium risk. Refer to the Word standards for surrounding scope and exceptions.

Follow the [backend import guide](../README.md#configure-document-reviews) to populate Chroma. The import sends rule text and evidence guidance to OpenAI for embeddings. The bundled Word files are marked **Internal**.
