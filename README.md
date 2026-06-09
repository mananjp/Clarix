# Clarix | Compliance, Clarified.

This repository contains the core compliance intelligence engine for Clarix, including GxA, RAG-extraction, and the validation rules engine.

## Usage
1. Ensure the environment is active: `.venv\Scripts\activate`
2. Run the master verification: `python tests_verify.py`

## Expected Output
`ALL CLARIX FEATURE VERIFICATIONS: PASSED ✓`

## Core Test Cases
- **Happy Path**: Full extraction of standard KPIs.
- **Rule Bounds**: Percentages over 100%.
- **Negativity Check**: Detection of negative ESG values.
- **Deduplication**: Ensuring unique uploads based on content hashing.
- **Narrative Depth**: Flagging reports with insufficient descriptive evidence.
- **Multi-Tenancy**: Enforcing strict organization-level data isolation.
