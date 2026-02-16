from typing import List, Tuple
from langgraph.graph import StateGraph, END

from src.state import QAState
from src.nodes import (
    node_planner, 
    node_reasoner, 
    node_searcher, 
    node_extractor, 
    node_answer
)

# ==============================
# 1) Graph Building
# =============================

def build_graph():
    """Build the Multi-Agent QA graph (간결 버전)"""
    g = StateGraph(QAState)
    
    # Add nodes
    g.add_node("planner", node_planner)
    g.add_node("reasoner", node_reasoner)
    g.add_node("searcher", node_searcher)
    g.add_node("extractor", node_extractor)
    g.add_node("answer", node_answer)  
    
    # Entry
    g.set_entry_point("planner")
    
    # Planner edges
    g.add_conditional_edges(
        "planner",
        lambda s: s.get("action", ""),
        {
            "reasoner": "reasoner",
            "finish": "answer"
        }
    )
    
    # Reasoner edges (Planner와 양방향)
    g.add_conditional_edges(
        "reasoner",
        lambda s: s.get("action", ""),
        {
            "search": "searcher",
            "next_step": "reasoner",
            "finish": "answer",      # → Answer (Chain)
            "planner": "planner"     # ← Planner (재계획)
        }
    )
    
    # Tool edges
    g.add_edge("searcher", "extractor")
    g.add_edge("extractor", "reasoner")
    
    # Answer → END (단방향)
    g.add_edge("answer", END)
    
    return g.compile()

# ==============================
# 2) Main Runner
# ==============================

def run_question(question: str, context: List[Tuple[str, List[str]]]) -> QAState:
    """Run a single question"""
    
    app = build_graph()
    
    state: QAState = {
        "question": question,
        "hotpot_context": context,
        "plan": [],
        "step_idx": 0,
        "trace": [],
        "verbose": True,
        "current_evidence": [],
        "step_answers": [],
        "replan_count": 0,  
        "total_iterations": 0
    }
    
    final_state = app.invoke(state, config={"recursion_limit": 75})
    
    return final_state
