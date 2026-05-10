# 6bq5 — In-flight Projects

## In-Progress

(empty — 초기 릴리스)

## Backlog (논문화 가능 우선순위 순)

### B1. AGNNCert randomized-smoothing 실 구현
**왜**: 현 `certified_radius()` 는 degree-기반 placeholder. 진짜 인증을 위해 sample budget B 와
robustness radius δ 를 학습된 smoothed-classifier 에서 측정.
**산출물**: `defense/agnncert.py` + 측정 표 (USENIX Security 2025 reproducibility).

### B2. DShield trigger-subgraph 학습 검출기
**왜**: 현 centrality z-score 는 너무 단순. NDSS 2025 의 discrepancy learning 채택.
**산출물**: `defense/dshield.py` + ROC AUC 표.

### B3. NeuroGen-style white-box poison fuzzer
**왜**: black-box 만 있는데 LLM 내부 뉴런 활성도 기반 GA 가 더 효과적 (NeurIPS 2025).
**산출물**: `poison/neurogen.py` + activation hook.

### B4. ASB 카탈로그 자동 평가
**왜**: ICLR 2025 ASB 의 10+ 공격을 한 번에 돌려 ASR/utility 비교 표 생성.
**산출물**: `experiments/asb_runner.py`, Experiments UI 의 “Run benchmark” 버튼.

### B5. RL node-injection 베이스라인
**왜**: WWW 2020 HRL 베이스라인 부재. budget-aware 비교 필요.
**산출물**: `poison/rl_inject.py`.

### B6. Multi-agent MITM 채널 시뮬
**왜**: AiTM (ACL 2025) 을 본 플랫폼 안에서 시연하려면 agent message bus 가 필요.
**산출물**: `agents/bus.py` + Memory Trace 와 통합.

## Closed

- ✅ 초기 플랫폼 골격 (KG sanitize · 6 recipe · 4 detector · 13 페이지) — 2026-05-10
