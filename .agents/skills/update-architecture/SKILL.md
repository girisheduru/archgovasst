---
name: update-architecture
description: Check and update the Architecture Governance Assistant's architecture image and workflow diagrams when LangGraph nodes, reviewer checkpoints, service boundaries, integrations, or data flows change.
---

# Update project architecture

1. Compare the change against [the architecture overview](../../../ARCHITECTURE.md), [the workflow diagrams](../../../flowdiagrams.md), and [the root README](../../../README.md). Open [the architecture image](../../../docs/images/architecture-current.png) and inspect the relevant panel. A text search of the Markdown misses labels embedded in the PNG.
2. Verify the affected details against the implementation. For LangGraph, compare the registered node names and edges in [the workflow graph](../../../backend/governance/agent/graph.py) and check the interrupt payloads and API checkpoint IDs. A node name and its checkpoint ID can differ.
3. Update each affected label, edge, or explanation in the same change. If the image shows an outdated detail, update the affected panel and save the revised image at the linked path. If the diagram still matches the implementation, leave it as is.
4. Open the revised image at full resolution. Check exact identifiers, legibility, arrow directions, and the surrounding labels. Verify that the Markdown links and diagrams agree with the revised image.
