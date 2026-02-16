import json
import re
from typing import List, Dict, Tuple, Optional
from src.state import QAState
from src.utils import call_llm
from src.prompts import (
    PLANNER_SYS, ANSWER_SYS, 
    get_replan_prompt, get_synthesize_prompt, get_verify_evidence_prompt,
    get_step_answer_prompt, get_select_doc_prompt, get_extractor_prompt,
    get_final_answer_prompt
)

# ==========================================
# [1] Planner Agent
# ==========================================
def node_planner(state: QAState) -> QAState:
    """
    Planner Agent: 계획 수립 및 수정 (개선 버전)
    """
    
    # 초기 계획
    if not state.get("plan"):
        print("\n🧠 [Planner] 초기 계획 수립...")
        
        q = state["question"]
        out = call_llm(PLANNER_SYS, f"Question:\n{q}\nReturn JSON only.")
        
        try:
            out_clean = out.strip()
            if out_clean.startswith("```"):
                lines = out_clean.split("\n")
                out_clean = "\n".join(lines[1:-1])
            
            j = json.loads(out_clean)
            plan = j.get("plan", [])
        except Exception as e:
            print(f"   ⚠️ JSON parsing error: {e}")
            plan = ["Find information to answer the question."]
        
        state["plan"] = plan[:3] if plan else ["Find information to answer the question."]
        state["step_idx"] = 0
        state["planner_status"] = "active"
        state["replan_count"] = 0
        state["total_iterations"] = 0
        state["preserved_findings"] = []  #  중요 정보 보존
        
        print(f"\n✅ 초기 계획 ({len(state['plan'])} steps):")
        for i, step in enumerate(state["plan"], 1):
            print(f"   Step {i}: {step}")
        
        state["action"] = "reasoner"
        return state
    
    # 재계획 요청 처리
    if state.get("reasoner_request") == "replan":
        replan_count = state.get("replan_count", 0)
        
        if replan_count > 2:
            print(f"\n⚠️ [Planner] 재계획 한계 도달 ({replan_count}번)")
            print(f"   → 수집한 정보로 답변 시도")
            state["action"] = "finish"
            return state
        
        print(f"\n🔄 [Planner] 재계획 요청 받음! ({replan_count }/2)")
        
        # 🆕 중요 정보 추출 및 보존
        progress = state.get("step_answers", [])
        current_step_idx = state.get("step_idx", 0)
        
        # 이전에 발견한 중요 정보 수집
        found_entities = []
        found_facts = []
        promising_evidence = []
        
        for ans in progress:
            found_entities.append(ans["answer"])
            if ans.get("evidence"):
                for ev in ans["evidence"]:
                    if "located in" in ev or "published by" in ev or "founded in" in ev:
                        promising_evidence.append(ev)
        
        # 현재까지 수집한 모든 증거에서 중요 정보 추출
        all_evidence = state.get("current_evidence", [])
        for ev in all_evidence:
            if any(keyword in ev.lower() for keyword in ["bronx", "botanical", "journal", "published"]):
                promising_evidence.append(ev)
        
        # 사용된 문서 중 유용했던 것들
        useful_docs = []
        failed_docs = state.get("failed_documents", {})
        for title, _ in state.get("hotpot_context", []):
            if title not in failed_docs.get(current_step_idx, []):
                # 문서가 실패하지 않았고, 관련 키워드가 있으면 유용
                if any(keyword in title.lower() for keyword in ["journal", "botanical", "scientific"]):
                    useful_docs.append(title)
        
        #  실패 패턴 분석
        failure_analysis = _analyze_failure_pattern(state, progress, all_evidence)
        
        #  동적 전략 생성
        dynamic_strategy = _generate_dynamic_strategy(
            question=state["question"],
            current_plan=state["plan"],
            stuck_step=current_step_idx,
            found_entities=found_entities,
            found_facts=found_facts,
            promising_evidence=promising_evidence,
            useful_docs=useful_docs,
            failure_analysis=failure_analysis,
            replan_count=replan_count,
            state = state
        )
        
        # 프롬프트 함수 호출
        REPLAN_PROMPT = get_replan_prompt(
            question=state["question"],
            plan_str=json.dumps(state["plan"], indent=2),
            current_step_idx=current_step_idx,
            progress_str=json.dumps([{"step": a["step"], "answer": a["answer"]} for a in progress], indent=2),
            found_entities_str=json.dumps(found_entities),
            promising_evidence_str=json.dumps(promising_evidence[:3]),
            useful_docs_str=json.dumps(useful_docs),
            failure_analysis=failure_analysis,
            dynamic_strategy=dynamic_strategy,
            replan_count=replan_count
        )
        
        out = call_llm(
            "You are a strategic replanner. Use found information, don't restart.",
            REPLAN_PROMPT,
            temperature=0.2
        )
        
        try:
            out_clean = out.strip()
            if out_clean.startswith("```"):
                lines = out_clean.split("\n")
                out_clean = "\n".join(lines[1:-1])
            
            j = json.loads(out_clean)
            new_plan = j.get("plan", state["plan"])
            
            #  기존 정보 보존하면서 계획 업데이트
            state["plan"] = new_plan
            state["step_idx"] = len(progress)  # 완료된 step부터 시작
            
            #  중요: 찾은 정보 보존
            state["preserved_findings"] = {
                "entities": found_entities,
                "facts": found_facts,
                "evidence": promising_evidence,
                "useful_docs": useful_docs
            }
            if "failed_documents" in state and state["step_idx"] in state["failed_documents"]:
                print(f"   🔄 [Planner] 새로운 전략을 위해 실패 문서 기록 초기화 (Step {state['step_idx'] + 1})")
                del state["failed_documents"][state['step_idx']]
            
            # retry 카운트 초기화
            state["retry_count"] = {}
            state["reasoner_request"] = ""
            
            print(f"\n✅ 계획 수정 (Step {state['step_idx'] + 1}부터):")
            print(f"   📌 보존된 정보: {len(found_entities)} entities, {len(promising_evidence)} evidence")
            for i, step in enumerate(new_plan, 1):
                marker = "✓" if i <= len(progress) else "→"
                print(f"   {marker} Step {i}: {step}")

        except Exception as e:
            print(f"   ⚠️ 재계획 실패: {e}")
            state["action"] = "finish"
            return state
        
        state["action"] = "reasoner"
        return state
    
    state["action"] = "reasoner"
    return state


def _analyze_failure_pattern(state: QAState, progress: list, evidence: list) -> str:
    """실패 패턴 분석"""
    
    retry_count = state.get("retry_count", {})
    step_idx = state.get("step_idx", 0)
    
    patterns = []
    
    # 패턴 1: 정보가 문서에 없음
    if all("does not provide" in str(ev).lower() for ev in evidence[-3:] if ev):
        patterns.append("Information not found in available documents")
    
    # 패턴 2: 잘못된 문서 선택
    if retry_count.get(f"step_{step_idx}", 0) > 5:
        patterns.append("Repeatedly selecting wrong documents")
    
    # 패턴 3: 의존성 체인 깨짐
    if step_idx > 0 and not progress:
        patterns.append("Dependency chain broken - no previous results to build on")
    
    # 패턴 4: 부분 정보만 있음
    if progress and "partially" in str(progress[-1].get("answer", "")):
        patterns.append("Only partial information available")
    
    return "Failure patterns detected: " + ", ".join(patterns) if patterns else "No clear failure pattern"


def _generate_dynamic_strategy(
    question: str,
    current_plan: list,
    stuck_step: int,
    found_entities: list,
    found_facts: list,
    promising_evidence: list,
    useful_docs: list,
    failure_analysis: str,
    replan_count: int,
    state: QAState = None
) -> str:
    """상황에 맞는 동적 전략 생성"""
    
    strategies = []
    
    # 전략 1: 엔티티 기반 접근
    if found_entities:
        entity_list = ", ".join(found_entities[:3])
        strategies.append(f"Search directly for information about these entities: {entity_list}")
    
    # 전략 2: 문서 활용
    if useful_docs:
        doc_list = ", ".join(useful_docs[:3])
        strategies.append(f"Focus on these promising documents: {doc_list}")
    
    # 전략 3: 역방향 접근
    if "not found" in failure_analysis and replan_count == 0:
        strategies.append("Try REVERSE approach: start from the answer type and work backwards")
    
    # 전략 4: 부분 정보 활용
    if promising_evidence and replan_count == 1:
        strategies.append("Use partial information to approximate the answer")
    
    # 전략 5: 키워드 중심
    keywords = _extract_keywords_hybrid(question, state)
    if keywords:
        strategies.append(f"Focus search on these key terms: {', '.join(keywords)}")
    
    return "\n".join(f"{i+1}. {s}" for i, s in enumerate(strategies))

def _extract_keywords_hybrid(question: str, state: QAState) -> list:
    """하이브리드 키워드 추출: 규칙 + 컨텍스트"""
    
    keywords = set()
    
    # 1. 정규식으로 기본 추출
    # 고유명사
    proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', question)
    keywords.update(proper_nouns)
    
    # 숫자
    numbers = re.findall(r'\b\d{4}\b', question)  # 년도
    keywords.update(numbers)
    
    # 2. 이미 찾은 정보에서 관련 키워드 추가
    if state.get("step_answers"):
        for ans in state["step_answers"]:
            # 답변에서 명사 추출
            answer_words = ans["answer"].split()
            keywords.update([w for w in answer_words if w[0].isupper()])
    
    # 3. 문서 제목에서 힌트 얻기
    doc_titles = [title for title, _ in state.get("hotpot_context", [])]
    for title in doc_titles:
        # 질문과 관련있는 문서 제목의 단어들
        title_words = title.split()
        for word in title_words:
            if word.lower() in question.lower():
                keywords.add(word)
    
    # 4. 질문 타입별 키워드
    question_lower = question.lower()
    if "when" in question_lower:
        keywords.add("year")
        keywords.add("date")
    elif "where" in question_lower:
        keywords.add("location")
        keywords.add("place")
    elif "who" in question_lower:
        keywords.add("person")
        keywords.add("name")
    
    return list(keywords)

# ==========================================
# [2] Reasoner Agent
# ==========================================
def node_reasoner(state: QAState) -> QAState:
    """
    Reasoner Agent: 실행 제어 및 Planner와 협력
    """
    MAX_REPLANS = 2
    plan = state["plan"]
    step_idx = state["step_idx"]
    
    #  전체 반복 횟수 추적
    total_iterations = state.get("total_iterations", 0) + 1
    state["total_iterations"] = total_iterations
    
    #  안전장치 1: 최대 반복 횟수
    if total_iterations >= 40:  # 50 이전에 종료
        print(f"\n⚠️ [Reasoner] 최대 반복 횟수 도달 ({total_iterations})")
        print(f"   → 답변 불가로 강제 종료")
        
        # 지금까지 모은 정보로 답변 시도
        if state.get("step_answers"):
            state["action"] = "finish"
        else:
            # 정보가 하나도 없으면 기본 답변
            state["answer"] = "Unable to answer - information not found in context"
            state["action"] = "finish"
        return state
    
    #  재계획 횟수 확인
    replan_count = state.get("replan_count", 0)
    
    # 재시도 한계
    retry_count = state.get("retry_count", {})
    step_key = f"step_{step_idx}"
    current_retry = retry_count.get(step_key, 0)
    
    # 사용 가능한 문서 확인
    failed_docs = state.get("failed_documents", {}).get(step_idx, [])
    total_docs = len(state.get("hotpot_context", []))
    remaining_docs = total_docs - len(failed_docs)
    
    #  재계획 조건 및 제한
    should_replan = (current_retry >= 10) or (remaining_docs == 0 and current_retry >= 2)
    
    if should_replan:
        # 재계획 한계 도달 체크
        if replan_count > MAX_REPLANS:
            print(f"\n⚠️ [Reasoner] 재계획 한계 도달 ({replan_count}/{MAX_REPLANS})")
            print(f"   → 부분 정보로 답변 시도")
            state["action"] = "finish"
            return state
        
        # 
        print(f"\n🆘 [Reasoner] Step {step_idx + 1} 막혔음!")
        print(f"   Retry: {current_retry}, Remaining docs: {remaining_docs}")
        
        # 
        print(f"   재계획 횟수: {replan_count }/{MAX_REPLANS}")
        print(f"   → Planner에게 재계획 요청")
        
        state["reasoner_request"] = "replan"
        state["replan_count"] = replan_count + 1
        state["action"] = "planner"
        return state



    # 모든 Step 완료
    if step_idx >= len(plan):
        print(f"\n   ✅ All {len(plan)} steps completed")
        state["action"] = "finish"
        return state
    
    current_step = plan[step_idx]
    
    print(f"\n🤖 [Reasoner] Step {step_idx+1}/{len(plan)} (Iteration {total_iterations})")
    print(f"   Goal: {current_step}")
    
    # Synthesis step 처리
    current_step_lower = current_step.lower()
    is_synthesis = (
        "from step 1 and 2" in current_step_lower or 
        "from step 1 and step 2" in current_step_lower or
        "from steps 1 and 2" in current_step_lower or
        "what they have in common" in current_step_lower or
        "determine if they were the same" in current_step_lower or
        "which was started first" in current_step_lower or
        "which came first" in current_step_lower
    )
    
    if is_synthesis:
        return _synthesize_step(state)
    
    # 증거 확인
    evidence = state.get("current_evidence", [])
    
    if not evidence:
        print(f"   → Searching...")
        state["action"] = "search"
        return state
    
    # "No relevant document" 메시지 확인
    if evidence and "No relevant document found" in evidence[0]:
        print(f"   ⚠️ Context에 관련 문서 없음")
        retry_count[step_key] = current_retry + 1
        state["retry_count"] = retry_count
        
        if current_retry >= 2:
            state["reasoner_request"] = "replan"
            state["replan_count"] = replan_count + 1  # 🆕
            state["action"] = "planner"
            return state
        
        state["action"] = "search"
        return state
    
    # LLM 증거 검증
    is_sufficient = _verify_evidence_with_llm(current_step, evidence)
    
    if not is_sufficient:
        print(f"   → Evidence insufficient")
        retry_count[step_key] = current_retry + 1
        state["retry_count"] = retry_count
        state["action"] = "search"
        return state
    
    # 답변 생성
    answer = _generate_step_answer(current_step, evidence)
    print(f"   ✅ Step Answer: {answer}")
    
    state.setdefault("step_answers", []).append({
        "step_idx": step_idx,
        "step": current_step,
        "answer": answer,
        "evidence": evidence
    })
    
    # 다음 Step
    state["step_idx"] += 1
    state["current_evidence"] = []
    
    # 🔧 수정: retry_count 안전하게 초기화
    if "retry_count" in state and step_key in state["retry_count"]:
        state["retry_count"].pop(step_key)
    
    # 또는 더 간단하게:
    # state.setdefault("retry_count", {}).pop(step_key, None)
    
    if state["step_idx"] >= len(state["plan"]):
        state["action"] = "finish"
    else:
        state["action"] = "next_step"
    
    return state

# [2.1]
def _synthesize_step(state: QAState) -> QAState:
    """
    Synthesis step 처리 (증거 포함)
    """
    current_step = state["plan"][state["step_idx"]]
    prev_answers = state.get("step_answers", [])
    
    print(f"   → Synthesis step")
    
    if len(prev_answers) < 2:
        print(f"   ⚠️ Not enough previous answers for synthesis!")
        state["action"] = "search"
        return state
    
    # ✅ 이전 답변 + 증거 모두 포함
    context_text = ""
    for a in prev_answers:
        context_text += f"\nStep {a['step_idx']+1}: {a['step']}\n"
        context_text += f"  Answer: {a['answer']}\n"
        if a.get('evidence'):
            context_text += f"  Evidence:\n"
            for ev in a['evidence'][:2]:  # 증거도 포함
                context_text += f"    - {ev}\n"
    # prompt func 호출
    PROMPT = get_synthesize_prompt(current_step, context_text)
    
    answer = call_llm(
        "You are a precise information synthesizer. Answer based ONLY on the evidence provided.",
        PROMPT,
        temperature=0.1
    )
    
    print(f"   ✅ Synthesized: {answer}")
    
    state.setdefault("step_answers", []).append({
        "step_idx": state["step_idx"],
        "step": current_step,
        "answer": answer,
        "evidence": []
    })
    
    state["step_idx"] += 1
    
    if state["step_idx"] >= len(state["plan"]):
        print(f"   → Last step completed")
        state["action"] = "finish"
    else:
        state["action"] = "next_step"
    
    return state

# [2.2]
def _verify_evidence_with_llm(step: str, evidence: List[str]) -> bool:
    """
    LLM으로 증거가 충분한지 판단 (개선)
    """
    
    if not evidence:
        return False
    
    evidence_text = "\n".join([f"- {e}" for e in evidence])
    # prompt func 호출
    PROMPT = get_verify_evidence_prompt(step, evidence_text)

    try:
        result = call_llm(
            "You are a strict but fair evidence judge. Be lenient with partial information.",
            PROMPT,
            temperature=0.0
        ).strip().lower()
        
        print(f"   🔍 [LLM Judge] Evidence sufficient: {result}")
        
        return "yes" in result
        
    except Exception as e:
        print(f"   ⚠️ [LLM Judge] Error: {e}, defaulting to True")
        return True  # Error 시 관대하게

#[2.3]
def _generate_step_answer(step: str, evidence: List[str]) -> str:
    """
    증거 기반 답변 생성 (개선)
    """
    evidence_text = "\n".join(evidence)
    # prompt func 호출
    PROMPT = get_step_answer_prompt(step, evidence_text)

    return call_llm("You are a precise extractor.", PROMPT, temperature=0.1).strip()

# ==========================================
# [3] Searcher Agent
# ==========================================
# tool?
def node_searcher(state: QAState) -> QAState:
    """
    Tool: Context에서 문서 선택 (사용한 문서 제외)
    """
    
    current_step = state["plan"][state["step_idx"]]
    context = state["hotpot_context"]
    step_idx = state["step_idx"]
    
    print(f"\n🔍 [Searcher] Finding document for: {current_step}")
    
    #  이미 실패한 문서들 가져오기
    failed_docs = state.get("failed_documents", {}).get(step_idx, [])
    
    #  사용 가능한 문서만 필터링
    available_context = [
        (title, sentences) 
        for title, sentences in context 
        if title not in failed_docs
    ]
    
    if not available_context:
        print(f"   ❌ 모든 문서 시도 완료, 사용 가능한 문서 없음")
        state["current_evidence"] = ["No relevant document found in context"]
        state["action"] = "reasoner"
        return state
    
    print(f"   📚 사용 가능한 문서: {len(available_context)}/{len(context)}")
    
    # LLM으로 문서 선택
    selected_doc = _select_doc_with_llm(
        current_step, 
        available_context,  # 🆕 필터링된 문서만 전달
        state.get("step_answers", [])
    )   

    if not selected_doc:
        print(f"   ❌ No document found")
        state["action"] = "reasoner"
        return state
    
    title, sentences = selected_doc
    print(f"   ✅ Selected: {title}")
    
    #  실패한 문서로 기록 (나중에 재시도 시 제외)
    failed_docs_dict = state.get("failed_documents", {})
    if step_idx not in failed_docs_dict:
        failed_docs_dict[step_idx] = []
    failed_docs_dict[step_idx].append(title)
    state["failed_documents"] = failed_docs_dict
    
    state["current_doc"] = {
        "title": title,
        "text": " ".join(sentences)
    }
    
    state["action"] = "extract"
    
    return state

# [3.1]
def _select_doc_with_llm(
    step: str,
    context: List[Tuple[str, List[str]]],
    previous_answers: List[Dict]
) -> Optional[Tuple[str, List[str]]]:
    """
    LLM으로 문서 선택 (이전 답변 활용)
    """
    
    if not context:
        return None
    
    titles = [title for title, _ in context]
    titles_str = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
    
    # 🆕 이전 답변 명시
    prev_str = ""
    key_entities = []
    if previous_answers:
        prev_str = "\n\n**Previous findings:**\n"
        for a in previous_answers[-2:]:
            prev_str += f"- {a['step']}: {a['answer']}\n"
            key_entities.append(a['answer'])
    
    # 🆕 "from step X" 감지
    if ("from step" in step.lower() or "those" in step.lower() or 
        "these" in step.lower()) and key_entities:
        prev_str += f"\n🚨 Current question refers to: {', '.join(key_entities)}\n"
        prev_str += f"Choose document most likely to have info about these entities!\n"
    # prompt func 호출
    PROMPT = get_select_doc_prompt(step, prev_str, titles_str, len(titles))
    
    try:
        result = call_llm(
            "You are a document selector who tracks entity references.",
            PROMPT,
            temperature=0.2
        ).strip()
        
        match = re.search(r'\d+', result)
        if match:
            doc_num = int(match.group()) - 1
            if 0 <= doc_num < len(context):
                return context[doc_num]
        
        print(f"   ⚠️ Failed to parse, using first doc")
        return context[0] if context else None
        
    except Exception as e:
        print(f"   ❌ LLM error: {e}")
        return context[0] if context else None
    

# ==========================================
# [4] Extractor Agent
# ==========================================
def node_extractor(state: QAState) -> QAState:
    """
    Tool: 문서에서 증거 추출 (이전 step 답변 활용)
    """
    
    current_step = state["plan"][state["step_idx"]]
    doc = state.get("current_doc", {})
    
    if not doc:
        print(f"\n📄 [Extractor] No document to extract from")
        state["action"] = "reasoner"
        return state
    
    print(f"\n📄 [Extractor] Extracting evidence")
    print(f"   From: {doc['title']}")
    
    # 🆕 이전 step 답변 명시적 처리
    prev_answers = state.get("step_answers", [])
    prev_context = ""
    reference_entities = []  # 🆕 이전 답변에서 추출한 핵심 엔티티
    
    if prev_answers:
        prev_context = "\n\n**PREVIOUS FINDINGS (CRITICAL - USE THESE!):**\n"
        for i, a in enumerate(prev_answers[-3:], 1):
            prev_context += f"Step {a['step_idx']+1}: {a['step']}\n"
            prev_context += f"  → Answer: {a['answer']}\n"
            
            # 🆕 답변에서 핵심 엔티티 추출
            reference_entities.append(a['answer'])
    
    # 🆕 "from step X" 키워드 감지
    references_prev_step = ("from step" in current_step.lower() or 
                           "those" in current_step.lower() or
                           "that" in current_step.lower() or
                           "these" in current_step.lower())
    
    reference_instruction = ""
    if references_prev_step and prev_answers:
        reference_instruction = f"""
🚨 **CRITICAL - REFERENCING PREVIOUS STEP:**
The current question uses "those/these/that/from step X" which refers to:
{chr(10).join([f"  - {ans}" for ans in reference_entities[-2:]])}

You MUST find information about THESE SPECIFIC entities mentioned above!
DO NOT find information about other entities in the document!

Example:
- Previous: "torpedo boats"
- Current: "objects carried by those ships"
- YOU MUST: Find what TORPEDO BOATS carry
- DO NOT: Find what other ships carry
"""
    task_text = f"Find information about: {', '.join(reference_entities[-2:])}" if references_prev_step and reference_entities else "Extract information that answers the current step"
    # prompt func 호출
    PROMPT = get_extractor_prompt(
        current_step=current_step,
        prev_context=prev_context,
        reference_instruction=reference_instruction,
        doc_title=doc['title'],
        doc_text=doc['text'][:1500],
        task_text=task_text
    )
    
    evidence = call_llm("You are a precise extractor who carefully tracks entity references across steps.", PROMPT, temperature=0.1).strip()
    print(f"   ✅ Evidence: {evidence[:100]}...")
    state.setdefault("current_evidence", []).append(evidence)
    state["action"] = "reasoner"
    return state
# ==========================================
# [5] Answer Agent
# ==========================================
# [5.1]
def _generate_final_answer(state: QAState) -> str:
    """
    최종 답변 생성 (증거 우선 확인)
    """
    question = state["question"]
    step_answers = state.get("step_answers", [])
    
    if not step_answers:
        return "Unable to answer - no information gathered"
    
    # 🆕 증거 포함
    steps_text = ""
    for i, ans in enumerate(step_answers, 1):
        steps_text += f"\nStep {i}: {ans['step']}\n"
        steps_text += f"  Answer: {ans['answer']}\n"
        
        # 🆕 증거 추가
        if ans.get('evidence'):
            steps_text += f"  📄 Evidence:\n"
            for ev in ans['evidence'][:2]:  # 최대 2개 증거
                steps_text += f"    - {ev[:200]}...\n"
    # prompt func 호출
    PROMPT = get_final_answer_prompt(question, steps_text)
    
    response = call_llm(
        ANSWER_SYS,
        PROMPT,
        temperature=0.1
    )
    
    # JSON 파싱
    try:
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        
        result = json.loads(response)
        final_answer = result.get("final_answer", "")
        
        print(f"\n🎯 [Answer Generator]")
        print(f"   Question Type: {result.get('question_type', 'unknown')}")
        print(f"   Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
        print(f"   Final Answer: {final_answer}")
        
        return final_answer
        
    except Exception as e:
        print(f"   ⚠️ JSON parsing error: {e}")
        if step_answers:
            return step_answers[-1]["answer"]
        return "Unable to generate answer"

# [5]
def node_answer(state: QAState) -> QAState:
    """
    Answer Node: 최종 답변 생성 (단순 변환)
    """
    print(f"\n🎯 [Answer] Generating final answer")
    
    # 단순히 최종 답변만 생성
    final_answer = _generate_final_answer(state)
    
    print(f"    Final Answer: {final_answer}")
    
    state["answer"] = final_answer
    state["action"] = "finish"
    
    return state