# 6bq5 — Research Survey (2024-2026 top-tier)

연구 근거. **본 플랫폼은 아래 페이퍼들의 공격/방어 원리를 직접 시연/측정 가능하도록 매핑했다.**
모든 인용은 IEEE Transactions / USENIX Security / IEEE S&P / NDSS / CCS / KDD / NeurIPS / ICML /
ICLR / AAAI / ACL / EMNLP / WWW 등에서 출간된 것만 채택.

## 1. KG / RAG poisoning

| Paper | Venue | Idea | Platform mapping |
|---|---|---|---|
| **PoisonedRAG** (Zou, Geng et al.) | USENIX Security 2025 | k 개 crafted text 만 KG/벡터 store 에 주입해도 ~90% ASR | `poisoned_rag` recipe |
| **One-Shot Dominance** | EMNLP Findings 2025 | 단일 문서가 multi-hop 까지 hijack | `one_shot_dominance` recipe |
| **ROAR** (Xi, Du) | USENIX Security 2023 | KG anchor 주위 bait evidence | `roar_anchor` recipe |
| **FKGE Poisoning** (Zhou, Guo et al.) | WWW 2024 | 연합 KGE 의 client 측 triple 주입으로 글로벌 embedding 편향 | `fkge_client` recipe |
| **NeuroGenPoisoning** | NeurIPS 2025 | LLM 내부 뉴런 활성도로 가이드된 GA poison | (white-box mode 후속 작업) |
| **RevPRAG** | EMNLP Findings 2025 | RAG poisoning detection | (defense 계열로 후속 통합) |

## 2. 그래프 적대 perturbation

| Paper | Venue | Idea | Platform mapping |
|---|---|---|---|
| **Adversarial Attacks on GNNs via Node Injection (HRL)** (Sun, Wang) | WWW 2020 | RL 기반 node injection | (budgeted attack 모드 후속) |
| **GRAPHTEXTACK** | 2025 (review) | LLM-rewritten 텍스트 features 로 black-box injection | (motivation only) |

## 3. 타겟 / 가치 매트릭스

| Paper | Venue | Idea | Platform mapping |
|---|---|---|---|
| **Clean-Label Graph Backdoor** | AAAI 2025 | 고-centrality 타겟 + 라벨 보존 트리거 | `clean_label_backdoor` recipe + Value Matrix 페이지 |
| **Effective Clean-Label Backdoor on GNNs** | CIKM 2024 | clustering 기반 victim 선택 | (centrality vs clustering 비교 후속) |

## 4. KG / GNN 방어

| Paper | Venue | Idea | Platform mapping |
|---|---|---|---|
| **AGNNCert** (Li, Wang) | USENIX Security 2025 | arbitrary perturbation 에 대한 인증 예측 | `/api/defense/cert/{node}` |
| **XGNNCert** | ICLR 2025 | 예측 + 설명 둘 다 인증 | (explanation stability 후속) |
| **DShield** | NDSS 2025 | discrepancy learning 으로 트리거 subgraph 탐지 | `scan_centrality_spike` (간이 z-score 버전) |
| **KnowGraph** | CCS 2024 | GNN + FOL 결합 anomaly | `defense_rules` (FOL kind) |
| **DPSBA** | NeurIPS 2025 | distribution-preserving 백도어 + TV-distance 기반 stealth 평가 | `/api/defense/distribution/{snap_id}` (KL of degree dist) |
| **UGBA** | WWW 2023 | 위장도 (notice-ability) 점수 | (notice-ability 후속) |

## 5. 멀티에이전트 / 메모리

| Paper | Venue | Idea | Platform mapping |
|---|---|---|---|
| **AiTM Multi-Agent Attacks** (He, Lin) | ACL 2025 | agent-in-the-middle 가 메시지 변조 | `mitm_concept_swap` recipe + Memory Trace |
| **Agent Security Bench (ASB)** | ICLR 2025 | 10+ 공격 카테고리 표준 평가 | (Experiments → recipe 카탈로그 확장 후속) |
| **MINJA** | 2025 (preprint) | query-only 메모리 주입 | `/api/memory/trace` |
| **IsolateGPT** | NDSS 2025 | 에이전트 실행 격리 | `tenant`/`namespace` 메타필드 (후속 sandbox API) |

## 시사점 — 본 플랫폼이 후속 채워야 할 것

1. **NeuroGen-style white-box** — LLM 내부 활성도 점수 기반 poison 후보 fuzzer
2. **Budgeted RL injection** — node-injection HRL 베이스라인
3. **AGNNCert 실 구현** — 현 placeholder 대신 randomized smoothing
4. **DShield real model** — discrepancy learning 학습된 검출기
5. **ASB 평가 자동화** — Experiments 페이지에서 카탈로그 일괄 실행

위 5가지는 paper-publishable 후속 과제로 `docs/inflight-projects.md` 에서 우선순위.
