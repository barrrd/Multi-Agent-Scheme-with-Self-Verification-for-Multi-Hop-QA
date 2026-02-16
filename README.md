# 🤖 Multi-Agent Scheme with Self-Verification for Multi-Hop Q&A

> **Access Key Materials**
> - [📄 **Research Paper (PDF)**](./docs/Paper.pdf)
> - [🖼️ **Research Poster (PNG)**](./docs/Poster.PNG)

A specialized multi-agent system designed to mitigate hallucinations and enhance accuracy in complex Multi-Hop QA, featuring a dynamic correction feedback loop.

## 📌 Abstract (Thesis Overview)
Large Language Models (LLMs) often struggle with information retrieval failures and hallucinations in multi-hop QA that requires complex reasoning across multiple documents. While the ReAct framework addresses some of these issues, its linear execution structure propagates initial retrieval errors to subsequent steps without correction, leading to final answer failures. Furthermore, the lack of a self-verification mechanism degrades system robustness. 

## 🏗️ Architecture & 5 Specialized Agents
The system adopts a layered architecture, categorizing agents into the **Cognitive & Control Layer** and the **Retrieval & Execution Layer**.

![System Architecture](./image/System%20Architecture.png)

*Figure 1. Overview of the proposed Multi-Agent System and Shared State Memory.*

### 1. Cognitive & Control Layer (The Brain)
- **🧠 Planner**: Decomposes complex questions into atomic sub-goals. It dynamically resets search paths or modifies strategies upon receiving a **Correction Request**.
- **⚙️ Reasoner**: The central control tower managing the execution flow and delegating tasks. It performs **Self-Verification** to ensure information sufficiency.
- **🎯 Answer**: Synthesizes verified evidence into a final, clear answer, following strict rules to eliminate unnecessary descriptions.

### 2. Retrieval & Execution Layer (The Hands & Feet)
- **🔍 Searcher**: Identifies relevant documents within complex contexts (e.g., HotpotQA) and tracks entities across steps.
- **📄 Extractor**: Precisely extracts factual sentences from selected documents to minimize noise and hallucination.

---

## 🛡️ Self-Verification & Dynamic Correction
To prevent error propagation typical in linear frameworks like ReAct, this system incorporates a cyclic feedback loop.

### 🔍 Self-Verification Mechanism
The Reasoner evaluates the **logical sufficiency** of evidence immediately after extraction. It blocks irrelevant data from transitioning to the next step, ensuring only verified data is used for reasoning.

### 🔄 Dynamic Correction Feedback Loop
Triggered by structural information voids or planning errors, this loop utilizes LangGraph's cyclic structure.

![Dynamic Feedback Loop](./image/Dynamic%20Feedback%20Loop.png)


*Figure 2. Dynamic Correction Feedback Loop between Planner and Reasoner.*

**Correction Triggers:**
* Exceeding retry thresholds without valid information extraction.
* Failure to find decisive evidence despite exhausting accessible documents.

**Advanced State Control Strategies:**
* **State Preservation**: Freezes and preserves successfully verified facts during re-planning.
* **Search Space Reset**: Re-initializes the status of 'irrelevant' documents for the failed step to allow re-discovery.
* **Inference with Partial Information**: Combines secured partial data with logical elimination to derive the best possible answer.

## 📂 Repository Structure
```text
multi-agent-self-verification/
├── src/               
│   ├── graph.py       # LangGraph cyclic pipeline build and node connections
│   ├── nodes.py       # Core logic for the 5 agents and dynamic correction control
│   ├── prompts.py     # System prompts and dynamic variable templates for each agent
│   ├── state.py       # System state (QAState) schema definition
│   └── utils.py       # Helper functions for LLM calls, data loading, and evaluation (EM/F1)
├── scripts/           
│   └── run_batch.py   # Batch execution and result saving script for the HotpotQA dataset
├── data/              # Dataset directory (HotpotQA json)
├── result/            
│   └── MultiHop_QA/   # Experimental results storage directory (results.json, summary.json)
├── requirements.txt   # List of dependencies
└── .env.example       # Environment variables template
