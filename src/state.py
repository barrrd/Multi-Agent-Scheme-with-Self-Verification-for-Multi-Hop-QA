from typing import Any, Optional, Tuple, List, Dict, TypedDict
class QAState(TypedDict, total=False):
    # 기존 필드들
    question: str
    plan: List[str]
    step_idx: int
    trace: List[str]
    verbose: bool
    hotpot_context: List[Tuple[str, List[str]]]
    action: str
    current_doc: Dict
    current_evidence: List[str]
    step_answers: List[Dict]
    answer: str
    retry_count: Dict[str, int]
    
    # Multi-Agent 통신
    reasoner_request: str
    planner_status: str
    
    #  문서 추적
    used_documents: List[str]  # 이미 사용한 문서 제목들
    failed_documents: Dict[int, List[str]]  # Step별 실패한 문서들
    preserved_findings: Dict[str, List[str]] #  재계획 시 찾은 정보 보존용 
    replan_count: int  # 재계획 횟수
    total_iterations: int  # 전체 반복 횟수