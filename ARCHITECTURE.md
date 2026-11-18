# AI Architecture Governance Assistant

![Current architecture of the AI Architecture Governance Assistant](docs/images/architecture-current.png)

The review runs through six LangGraph nodes with two human decisions. OpenAI extracts candidate evidence, the backend validates citations, and the policy engine computes findings and risk. Chroma stores versioned standards. Live review state resides in backend memory until a restart. Evaluation runs separately against an exported report and a human answer key.
