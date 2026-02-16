import os
import json
import time
import random
import traceback
from pathlib import Path

from src.graph import run_question
from src.utils import load_hotpot_qa, evaluate

import os
import json
import time
import random
import traceback
from pathlib import Path

# 우리가 만든 모듈들 가져오기
from src.graph import run_question
from src.utils import load_hotpot_qa, evaluate

if __name__ == "__main__":
    # ----------------- 실험 설정 -----------------
    DATASET_PATH = Path("data/hotpot_dev_distractor_v1.json")
    TOTAL_SIZE = 7405
    NUM_SAMPLES = 100
    SHUFFLE_SEED = 233
    PRINT_EVERY = 1
    SAVE_EVERY = 5
    
    OUTPUT_DIR = 'result/MultiHop_QA'
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'results.json')
    PARTIAL_FILE = os.path.join(OUTPUT_DIR, 'results_partial.json')
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ----------------- 데이터 로드 -----------------
    print("="*70)
    print(" Multi-Hop QA System - Batch Execution")
    print("="*70)
    print(f"Dataset: {DATASET_PATH}")
    print(f"Samples: {NUM_SAMPLES}")
    print(f"Output: {OUTPUT_DIR}")
    print("="*70)
    
    dataset = load_hotpot_qa(DATASET_PATH)
    
    # 인덱스 섞기
    idxs = list(range(min(TOTAL_SIZE, len(dataset))))
    random.Random(SHUFFLE_SEED).shuffle(idxs)
    idxs = idxs[:NUM_SAMPLES]
    
    # 결과 저장용
    rs = []  # F1 scores
    infos = []  # 상세 정보
    start_time = time.time()
    
    # ----------------- Main Loop -----------------
    try:
        for k, idx in enumerate(idxs, 1):
            sample = dataset[idx]
            
            print(f"\n{'#'*70}")
            print(f"🔬 테스트 {k}/{len(idxs)} (Index: {idx})")
            print(f"{'#'*70}")
            print(f"Question: {sample['question']}")
            print(f"Gold: {sample['answer']}")
            print(f"Type: {sample.get('type', 'unknown')}")
            print(f"{'='*70}\n")
            
            try:
                # ========================================
                # 핵심 실행 (graph.py에서 가져온 함수)
                # ========================================
                result = run_question(
                    question=sample["question"],
                    context=sample["context"]
                )
                
                # ========================================
                # 결과 평가 (utils.py에서 가져온 함수)
                # ========================================
                predicted = result.get("answer", "")
                gold = sample["answer"]
                metrics = evaluate(predicted, gold)
                
                print(f"\n{'='*70}")
                print(f"📊 결과 요약")
                print(f"{'='*70}")
                print(f"Predicted: {predicted}")
                print(f"Gold: {gold}")
                print(f"EM: {metrics['em']}, F1: {metrics['f1']:.4f}")
                print(f"{'='*70}")
                
                # 결과 저장
                f1_val = metrics['f1']
                rs.append(f1_val)
                
                info = {
                    "index": idx,
                    "question": sample["question"],
                    "gold": gold,
                    "predicted": predicted,
                    "em": metrics["em"],
                    "f1": metrics["f1"],
                    "type": sample.get("type", "unknown"),
                    "level": sample.get("level", "unknown"),
                    "plan": result.get("plan", []),
                    "step_count": len(result.get("step_answers", []))
                }
                infos.append(info)
                
                # 중간 통계
                avg_f1 = sum(rs) / len(rs)
                avg_em = sum(info["em"] for info in infos) / len(infos)
                avg_time = (time.time() - start_time) / len(rs)
                
                if (k % PRINT_EVERY) == 0:
                    print(f"\n{'='*70}")
                    print(f"📈 진행 상황 [{k}/{len(idxs)}]")
                    print(f"{'='*70}")
                    print(f"Average EM: {avg_em:.4f}")
                    print(f"Average F1: {avg_f1:.4f}")
                    print(f"Avg Time: {avg_time:.3f}s per question")
                    print(f"{'='*70}\n")
                
                # 부분 저장
                if (k % SAVE_EVERY) == 0:
                    with open(PARTIAL_FILE, 'w', encoding='utf-8') as pf:
                        json.dump(infos, pf, ensure_ascii=False, indent=2)
                    print(f"💾 [Partial Save] {k}개 완료 → {PARTIAL_FILE}\n")
            
            except Exception as e:
                print(f"\n❌ [ERROR] 샘플 {idx} 실행 실패")
                print(f"Error: {str(e)}")
                traceback.print_exc()
                
                infos.append({
                    "index": idx,
                    "question": sample["question"],
                    "gold": sample["answer"],
                    "predicted": "",
                    "em": 0,
                    "f1": 0.0,
                    "type": sample.get("type", "unknown"),
                    "error": str(e)
                })
                rs.append(0.0)
                continue
                
    except KeyboardInterrupt:
        print("\n⚠️ [중단됨] KeyboardInterrupt → 부분 저장 중...")
        with open(PARTIAL_FILE, 'w', encoding='utf-8') as pf:
            json.dump(infos, pf, ensure_ascii=False, indent=2)
        print(f"💾 부분 결과 저장 완료: {PARTIAL_FILE}")
        raise
    
    except Exception as e:
        print("\n❌ [ERROR] 실행 중 치명적 오류 발생")
        traceback.print_exc()
        with open(PARTIAL_FILE, 'w', encoding='utf-8') as pf:
            json.dump(infos, pf, ensure_ascii=False, indent=2)
        print(f"💾 부분 결과 저장 완료: {PARTIAL_FILE}")
        raise
    
    # ----------------- 최종 결과 -----------------
    print("\n" + "="*70)
    print("🎉 실험 완료!")
    print("="*70)
    
    final_em = sum(info["em"] for info in infos if "em" in info) / len(infos) if infos else 0.0
    final_f1 = sum(rs) / len(rs) if rs else 0.0
    total_time = time.time() - start_time
    
    print(f"총 샘플: {len(rs)}")
    print(f"최종 EM: {final_em:.4f}")
    print(f"최종 F1: {final_f1:.4f}")
    print(f"총 시간: {total_time:.2f}s")
    print(f"평균 시간: {total_time/len(rs):.2f}s per question")
    
    from collections import defaultdict
    by_type = defaultdict(list)
    for info in infos:
        if "type" in info and "f1" in info:
            by_type[info["type"]].append(info["f1"])
    
    if by_type:
        print(f"\n{'='*70}")
        print("📊 타입별 성능")
        print(f"{'='*70}")
        for qtype, f1_scores in sorted(by_type.items()):
            avg = sum(f1_scores) / len(f1_scores)
            print(f"{qtype:20s}: F1={avg:.4f} (n={len(f1_scores)})")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(infos, f, ensure_ascii=False, indent=2)
    
    summary = {
        "num_samples": len(rs),
        "final_em": final_em,
        "final_f1": final_f1,
        "total_time": total_time,
        "avg_time": total_time / len(rs) if rs else 0,
        "by_type": {
            qtype: {
                "avg_f1": sum(scores) / len(scores),
                "count": len(scores)
            }
            for qtype, scores in by_type.items()
        }
    }
    
    summary_file = os.path.join(OUTPUT_DIR, 'summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 최종 결과 저장: {OUTPUT_FILE}")
    print(f"✅ 요약 저장: {summary_file}")
    print("="*70)