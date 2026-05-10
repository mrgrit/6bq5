# 6bq5 — KG Manipulation Risk · Targeted Pentest · Defense Lab

CCC 의 Knowledge Graph 를 의도적으로 변조했을 때 LLM-기반 사이버 공격이 어떻게
달라지는지 실험하고, 그에 대한 보호 체계를 개발하기 위한 통합 플랫폼.

세 저장소를 한 화면에서 운용한다:

| 출처 | 사용처 |
|------|--------|
| **`~/ccc`** Knowledge Graph (`data/bastion_graph.db`) | scripts/import_kg.py 가 precinct6 외부 데이터를 제외하고 `data/kg.db` 로 sanitize 복사 |
| **`~/bastion`** AI agent (`bastion-api`) | LLM 호출 + KG 사전참조/사후 anchor 정책 그대로 활용 (`/api/bastion/chat`) |
| **`~/6v6`** docker 인프라 | attacker / fw / web / siem 컨테이너에 plan 실제 실행 (`/api/infra/*`, `/api/pentest/exec`) |

## 연구 근거 (2024–2026 IEEE/USENIX/ACL/NDSS 등 톱티어)

| 페이퍼 | 본 플랫폼 매핑 |
|--------|----------------|
| **PoisonedRAG** (USENIX Security 2025, Zou et al.) | `poisoned_rag` recipe — k-doc retrieval injection |
| **One-Shot Dominance** (EMNLP Findings 2025) | `one_shot_dominance` — 단일 bridging 문서 주입 |
| **ROAR** (USENIX Security 2023) | `roar_anchor` — anchor 주변 bait evidence |
| **Clean-Label Graph Backdoor** (AAAI 2025) | `clean_label_backdoor` — 고-centrality 타겟 + 라벨 보존 트리거 |
| **FKGE Poisoning** (WWW 2024) | `fkge_client` — 클라이언트 측 triple injection |
| **AiTM Multi-Agent Attacks** (ACL 2025) | `mitm_concept_swap` — 메시지/Concept 라벨 변조 |
| **AGNNCert** (USENIX Security 2025) | `/api/defense/cert/{node}` — 인증 robustness 배지 |
| **DShield** (NDSS 2025) | `scan_centrality_spike` — z-score 기반 트리거 탐지 |
| **DPSBA** (NeurIPS 2025) | `/api/defense/distribution/{snap_id}` — degree-distribution KL stealth metric |
| **KnowGraph** (CCS 2024) | FOL `defense_rules` — `no_orphan_mitre`, `asset_unique_ip` 등 |
| **MINJA / IsolateGPT** (NDSS 2025) | `/memory/trace` — 에이전트 long-term memory write/read/rollback |

전체 서베이는 `docs/research-survey.md` 참조.

## 빠른 시작 — 리눅스만 깔린 머신에서

```bash
git clone https://github.com/mrgrit/6bq5.git
cd 6bq5

# (필요 시) 시스템 패키지 1회 설치
./setup.sh           # apt/dnf/pacman 자동 감지, python3+venv+pip

# 부팅 — Python venv 자동 생성 + 의존성 자동 설치 + uvicorn
./run.sh             # → http://0.0.0.0:8500/
```

`run.sh` 흐름:
1. `python3` 확인 → `.venv/` 생성 → `backend/requirements.txt` 설치
2. `data/kg.db` (precinct6-제거된 3,805 노드 KG, 6.5MB) 확인
3. `frontend/dist/` 확인 — repo 에 빌드 산출물 동봉되어 있어 **node/npm 불필요**
4. `uvicorn backend.main:app` 실행

**Node 가 필요한 경우** (frontend src 수정 시만):
```bash
WANT_NODE=1 ./setup.sh        # node 20.x 추가 설치
cd frontend && npm install && npm run build
```

### 수동 단계별

```bash
# 백엔드만
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8500

# 프론트엔드 (개발 모드, hot reload)
cd frontend && npm install && npm run dev
#   → http://localhost:5173 (vite 가 /api 를 :8500 으로 proxy)
```

### CCC 원본에서 KG 재import (선택)

저장소의 `data/kg.db` 는 2026-05-10 시점 sanitize 스냅샷. CCC 원본에서
다시 가져오려면:

```bash
SRC_KG=/path/to/bastion_graph.db python3 scripts/import_kg.py
```

`SRC_KG` 미지정 시 `~/ccc/data/bastion_graph.db` 등을 자동 탐색.

### 6v6 인프라 + bastion agent 연동 (선택)

`Pentest Workbench` 의 “execute” 와 `6v6 Console` 페이지는 외부 docker-compose
인프라가 있어야 작동. 두 저장소를 추가로 clone:

```bash
git clone https://github.com/mrgrit/6v6      # 옆 디렉토리
git clone https://github.com/mrgrit/bastion  # 옆 디렉토리
docker-compose -f 6v6/docker-compose.yaml up -d
INFRA_DIR=$PWD/6v6  BASTION_URL=http://localhost:9100  ./run.sh
```

**6v6 → KG 자동 등록**: 6v6 가 떠 있는 상태에서 `6v6 Console → ↻ Sync to KG`
버튼을 누르면 (또는 `curl -X POST :8500/api/infra/sync`):
- 모든 6v6 컨테이너를 `asset:6v6:<role>` 노드로 upsert (IP · 이미지 · 호스트네임 · 네트워크 · 상태 · 포트)
- docker network 마다 `net:6v6:<netname>` Concept 노드 생성 (cidr 포함)
- 같은 네트워크에 있는 노드끼리 `connects_to` 엣지 자동 연결
- 사라진 컨테이너는 `meta.stale=true` 로 마킹 (삭제 X — diff 가능)

→ 이후 Pentest / Manipulation / Defense 가 **실시간 인프라 토폴로지 위에서 동작**.

미설치여도 KG 변조 / 가치 매트릭스 / poison recipe / defense detector / 스냅샷
diff / RAG trace / memory trace / notes 등 **대부분의 기능은 바로 동작**.

## 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `KG_DB` | `./data/kg.db` | KG sqlite 위치 |
| `LLM_BASE_URL` | `http://localhost:11434` | Ollama (또는 호환) URL — 미연결 시 mock 응답 |
| `LLM_MODEL` | `gemma3:4b` | 모델명 |
| `BASTION_URL` | `http://localhost:9100` | CCC bastion FastAPI |
| `BASTION_API_KEY` | `ccc-api-key-2026` | bastion 인증 |
| `INFRA_DIR` | `/home/opsclaw/6v6` | 6v6 docker-compose 경로 |

## UI 페이지

| 그룹 | 페이지 | 설명 |
|------|--------|------|
| Core | Dashboard | KG/실험/방어 카운터, 노드/엣지 분포 차트 |
| KG | KG Explorer | CRUD, FTS 검색 |
| KG | Graph View | reactflow 기반 N-hop 시각화 |
| KG | Value Matrix | PageRank/betweenness/degree — 공격 ROI 식별 |
| KG | Snapshots | take · diff · restore (실험 전후 비교) |
| Attack | Manipulation Lab | 6 종 poison recipe, stealth/ASR 표시 |
| Attack | Pentest Workbench | KG context → LLM plan → 6v6 attacker exec |
| Attack | RAG Trace | 답변 attribution, poison context 라벨링 |
| Attack | Memory Trace | 에이전트 메모리 write/read/rollback log |
| Defense | Defense Studio | FOL · centrality spike · cert · dist KL |
| Ops | 6v6 Console | docker compose up/down/logs/exec |
| Ops | Bastion Chat | KG-integrated agent chat |
| Ops | Journal/Notes | tag 기반 markdown 노트 (실험과 link) |

## 권장 워크플로우

1. **Snapshots** → `pre-poison` baseline 저장
2. **Manipulation Lab** → 가설에 맞는 recipe 실행
3. **Snapshots** → `diff` 로 변조 양상 확인
4. **Value Matrix** → 변조 후 가치가 변한 노드 재정렬
5. **Pentest Workbench** → 타겟 선택, LLM 이 KG context (변조됨) 로 plan 생성
6. **6v6 Console** → plan step 실제 실행, 로그 확인
7. **Defense Studio** → run all detectors → 어떤 검출기가 잡았는지 평가
8. **Notes** → 가설/관측/결과 기록 (experiment_id 로 묶음)
9. **Snapshots** → restore 로 정상 KG 복구

## precinct6 데이터 처리

`scripts/import_kg.py` 가 다음을 자동 제외:
- `id` 가 `asset:p6:` 로 시작하는 노드
- `meta` JSON 안에 `precinct6` 가 들어간 노드
- `history_anchors` 의 `kind='ioc'` 행 (precinct6 IoC dump)
- 위에 매달려 있던 dangling edge

원본 KG 의 schema, node/edge 타입 (Asset / Concept / Skill / Playbook / Mission / Vision / Goal / KPI / Strategy / Plan / Todo / Experience / Insight / Recovery / Error / Narrative / Anchor) 와 30 종 edge 타입 (uses / handles / targets / supersedes / depends_on / often_chains / derived_from / encountered / recovered_by / applied_in / parent_of / abstracts / reuse / adapt / generalize / refute / precedes / follows / belongs_to / relates_to / connects_to / data_flows_to / hosts / manages / trusts / monitors / realizes / measures / contributes_to / blocks / owned_by / scheduled_for / derives_from) 는 그대로 유지된다.

## 라이선스

MIT (학술/연구 목적). 본 도구는 권한 있는 격리 환경(CCC 6v6 cyber range)에서의
교육·연구용. 무허가 시스템 대상 사용 금지.
