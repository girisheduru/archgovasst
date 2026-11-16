# Governance standards

The four Word files are the source documents for the Chroma standards collection. [`rules.json`](rules.json) contains the 26 numbered rules from STD-01 through STD-04, one row per rule version. Rule statements, evidence guidance, and effective dates come directly from the source documents. Use the original documents for the surrounding scope and exceptions.

The catalog makes each rule available to solution design and architecture decision reviews. The source documents give no per-rule gap severity, so the catalog uses `medium` for every missing-evidence finding as a provisional application default.

Follow the [backend import guide](../README.md#configure-document-reviews) to populate Chroma from this catalog. The import sends rule text and evidence guidance to OpenAI to create embeddings. The Word files are marked **Internal**.
