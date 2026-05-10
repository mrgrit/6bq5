# 6bq5 — 빠른 설치 (5분 컷)

> 상세 매뉴얼: [docs/MANUAL.md](MANUAL.md)

## 한 줄 요약 (추천)

```bash
git clone https://github.com/mrgrit/6bq5.git && cd 6bq5 && ./setup.sh && ./run.sh
```

- `./setup.sh` 가 `apt`/`dnf`/`pacman` 자동 감지 → `python3 python3-venv python3-pip` 설치 (sudo 1회)
- `./run.sh` 가 `.venv/` 자동 생성 + Python deps 설치 + uvicorn 부팅
- 브라우저: `http://<host>:8500/`

## 설치 옵션 매트릭스

| 시나리오 | 6bq5 | 6v6 | bastion | Ollama |
|----------|:---:|:---:|:-------:|:------:|
| **A. 학습/시연 (5분)** | ✓ | × | × | × |
| **B. + 모의해킹 실행** | ✓ | ✓ | × | mock OK |
| **C. + 변조 KG 로 bastion 시험** | ✓ | ✓ | ✓ | 권장 |
| **D. + 외부 노출 운영** | ✓ + systemd | ✓ | ✓ | ✓ |

### A. 6bq5 만 (5분)

```bash
git clone https://github.com/mrgrit/6bq5.git
cd 6bq5
./setup.sh
./run.sh
```

→ 11/13 페이지 동작 (Pentest exec, Bastion Chat 만 비활성).

### B. + 6v6 (사이버 레인지)

```bash
# 6v6 부팅 (5분, 16 컨테이너)
git clone https://github.com/mrgrit/6v6.git ~/6v6
cd ~/6v6 && docker compose up -d

# 6bq5 (이미 떠 있다면 skip)
cd ~/6bq5 && ./run.sh

# 인프라 ↔ KG 1회 동기화 (필수)
curl -X POST http://localhost:8500/api/infra/sync
# 또는 UI: 6v6 Console → ↻ Sync to KG
```

→ 13/13 페이지 동작. Pentest Workbench 의 “execute” 가 attacker 컨테이너에서 실제 실행됨.

### C. + bastion (변조 KG 위에서)

```bash
# 본인 환경에 맞는 bastion (CCC 안의 것 또는 ~/bastion)
BASTION_GRAPH_DB=$HOME/6bq5/data/kg.db \
  python3 -m uvicorn apps.bastion.api:app --host 0.0.0.0 --port 9100 &
```

→ Bastion Chat 이 6bq5 의 sanitize/변조 KG 를 사용.

### D. 운영 모드

```bash
# 1. systemd 서비스 등록
sudo tee /etc/systemd/system/6bq5.service > /dev/null <<EOF
[Unit]
Description=6bq5 KG Risk Lab
After=network.target docker.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$HOME/6bq5
Environment="INFRA_DIR=$HOME/6v6"
Environment="BASTION_URL=http://localhost:9100"
Environment="LLM_BASE_URL=http://localhost:11434"
ExecStart=$HOME/6bq5/run.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable --now 6bq5

# 2. 방화벽 (선택, 외부 노출 시)
sudo ufw allow 8500/tcp

# 3. nginx reverse proxy (TLS 필요 시)
# /etc/nginx/sites-available/6bq5 에 location / proxy_pass http://127.0.0.1:8500;
```

## 점검 체크리스트

설치 후:

```bash
# 1. 백엔드 헬스
curl -s http://localhost:8500/api/health | python3 -m json.tool
# bastion_reachable / llm_reachable / infra_dir 확인

# 2. KG 무결성
sqlite3 ~/6bq5/data/kg.db "PRAGMA integrity_check"
# → ok

# 3. KG 통계
curl -s http://localhost:8500/api/kg/stats | python3 -c "import json,sys; d=json.load(sys.stdin); print('nodes:',d['total_nodes'],'edges:',d['total_edges'])"
# → nodes: 3805+ edges: 497+

# 4. 6v6 동기화 (option B+)
curl -s -X POST http://localhost:8500/api/infra/sync | python3 -m json.tool
# → containers_synced: 16

# 5. UI 접근
curl -s http://localhost:8500/ | head -3
# → <!doctype html> ...
```

## 자주 나는 함정 (Top 5)

| 함정 | 해결 |
|------|------|
| `python3-venv` 미설치 → `./run.sh` 1단계 실패 | `sudo apt install python3-venv` |
| 외부 IP 로 접근 안 됨 | `sudo ufw allow 8500/tcp` 또는 iptables |
| `docker compose` 가 권한 부족 | `sudo usermod -aG docker $USER && newgrp docker` |
| KG 가 비어 보임 | `git checkout data/kg.db` 로 sanitize 스냅샷 복구 |
| 인프라 동기화 0 컨테이너 | 6v6 안 떠 있음. `docker compose up -d` (in ~/6v6) |

## 다음 단계

- 첫 실험: [docs/MANUAL.md §8.1 시나리오 A](MANUAL.md#81-시나리오-a--poisonedrag-단순-시연-15분)
- 전체 매뉴얼: [docs/MANUAL.md](MANUAL.md)
- 연구 근거: [docs/research-survey.md](research-survey.md)
- 후속 과제: [docs/inflight-projects.md](inflight-projects.md)
