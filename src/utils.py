import os
import re
import json
from pathlib import Path
from typing import List, Dict, Tuple
from collections import Counter
from dotenv import load_dotenv
load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def call_llm(system_prompt: str, user_prompt: str, model: str = OPENAI_MODEL, temperature: float = 0.2) -> str:
    """LLM 호출"""
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
    )
    return resp.choices[0].message.content.strip()

from pathlib import Path
import json

DATASET_PATH = Path("data/hotpot_dev_distractor_v1.json")

def load_hotpot_qa(path: Path = DATASET_PATH) -> List[Dict]:
    """
    HotpotQA 데이터셋 로드
    
    Returns:
        List of items, each with:
        - question: str
        - answer: str
        - context: List[Tuple[str, List[str]]]
        - supporting_facts: List[Tuple[str, int]]
        - type: str
        - _id: str
    """
    
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    
    print(f"[DATA] Loading from {path}...")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    items = []
    for item in data:
        # Context 파싱: [title, [sentences]] 형태로
        context = []
        for ctx in item.get("context", []):
            if len(ctx) == 2:
                title, sentences = ctx
                context.append((title, sentences))
        
        # Supporting facts 파싱
        supporting_facts = item.get("supporting_facts", [])
        
        items.append({
            "_id": item.get("_id", ""),
            "question": item.get("question", "").strip(),
            "answer": item.get("answer", ""),
            "context": context,
            "supporting_facts": supporting_facts,
            "type": item.get("type", ""),
            "level": item.get("level", "")
        })
    
    print(f"[DATA] Loaded {len(items)} items")
    
    # 샘플 출력
    if items:
        sample = items[0]
        print(f"\n[SAMPLE]")
        print(f"  Question: {sample['question'][:80]}...")
        print(f"  Answer: {sample['answer']}")
        print(f"  Context docs: {len(sample['context'])}")
        print(f"  Type: {sample['type']}")
    
    return items

def evaluate(pred: str, gold: str) -> Dict:
    """EM, F1 계산"""
    from collections import Counter
    import re
    
    # Normalize
    def normalize(s):
        if not s:
            return ""
        s = s.lower().strip()
        s = re.sub(r'\s+', ' ', s)
        # Remove articles
        s = re.sub(r'\b(a|an|the)\b', ' ', s)
        s = s.strip()
        return s
    
    pred_norm = normalize(pred)
    gold_norm = normalize(gold)
    
    # EM
    em = int(pred_norm == gold_norm)
    
    # F1
    pred_tokens = pred_norm.split()
    gold_tokens = gold_norm.split()
    
    if not pred_tokens or not gold_tokens:
        f1 = 0.0
    else:
        common = Counter(pred_tokens) & Counter(gold_tokens)
        num_same = sum(common.values())
        
        if num_same == 0:
            f1 = 0.0
        else:
            precision = num_same / len(pred_tokens)
            recall = num_same / len(gold_tokens)
            f1 = 2 * precision * recall / (precision + recall)
    
    return {"em": em, "f1": f1}