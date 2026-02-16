# 🤖 Multi-Agent Scheme with Self-Verification for Multi-Hop Q&A

A multi-agent system designed to mitigate hallucination and enhance information accuracy in complex Multi-Hop Question Answering (QA) tasks, leveraging LangGraph and the OpenAI API with a dynamic correction feedback loop.

## 📌 Abstract (Project Overview)
Large Language Models (LLMs) often struggle with information retrieval failures and hallucinations in multi-hop QA that requires complex reasoning across multiple documents. While the ReAct framework addresses some of these issues, its linear execution structure propagates initial retrieval errors to subsequent steps without correction, leading to final answer failures. Furthermore, the lack of a self-verification mechanism degrades system robustness. 

To overcome this, we propose a **multi-agent scheme equipped with a Self-Verification mechanism**. Five specialized agents (Planner, Reasoner, Searcher, Extractor, and Answer) collaborate and evaluate the reliability of collected information during the self-verification phase. Through a **dynamic correction feedback loop (cyclic graph structure)** that either proceeds with reasoning or modifies the search strategy based on verification results, errors are proactively blocked, enhancing the capacity for accurate answer generation. 

Experimental results on the HotpotQA dataset demonstrate that our proposed system achieves an **11.00-point improvement in Exact Match (EM) (a 23.9% increase) and a 15.07-point improvement in F1 score** compared to the baseline ReAct framework. This study proves that structured interaction and verification procedures among specialized agents are essential for improving the accuracy and reliability of multi-hop reasoning.

## 🏗️ Architecture & 5 Agents
This system is designed based on LangGraph and consists of five specialized agents (Nodes):

- **🧠 Planner**: Analyzes the user's question and decomposes it into multi-step sub-goals. If a search fails, it dynamically re-plans a new search strategy while preserving meaningful clues found in previous steps.
- **⚙️ Reasoner**: Acts as the control tower of the system. It performs self-verification to determine if the collected evidence is sufficient to achieve the current step's goal. Based on the result, it decides whether to proceed to the next step or request a re-search/re-plan.
- **🔍 Searcher**: Identifies and selects the most relevant document for the current reasoning step from the given document pool (Context).
- **📄 Extractor**: Precisely extracts only the core evidence (1-2 sentences) relevant to the question from the extensive text of the selected document.
- **🎯 Answer**: Synthesizes the verified evidence collected across all steps to derive the final answer and its reasoning process.

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