# 📝 Project Plan: Sentinel-Custody-Engine

본 프로젝트는 금융기관 수준의 보안 및 감사 요건을 충족하는 **오프체인 수탁 관제 시스템**을 구축하는 것을 목표로 합니다.

---

## 1. 🧠 Brainstorming & Philosophy

### 🧐 핵심 문제 정의

- **금고(On-chain)의 한계**: 스마트 컨트랙트만으로는 복잡한 보안 정책(화이트리스트, 한도 관리)을 가스비 효율적으로 구현하기 어렵습니다.
- **신뢰의 분산**: 단일 관리자 키가 탈취되어도 자산이 안전하려면, 키를 쪼개어 관리하는 **MPC(Multi-Party Computation)** 구조가 필수적입니다.
- **데이터 불일치**: 블록체인 네트워크의 지연이나 실패 상황에서도 내부 장부(Ledger)와 실제 잔액이 항상 일치해야 합니다.

### 💡 해결 전략

- **Sentinel Gate**: 모든 출금 요청을 서명 전 단계(`Pre-Sign`)에서 검증하여 위험 요소를 차단합니다.
- **Threshold Security**: 2-of-3 구조를 통해 운영 가용성과 보안성을 동시에 확보합니다.
- **Double-Check Audit**: 온체인 인덱서와 내부 원장을 실시간으로 대조(Reconciliation)하여 정합성을 확정합니다.

---

## 🏗️ 2. Architecture & Tech Stack

| 구분             | 기술 스택             | 선정 사유                                     |
| :--------------- | :-------------------- | :-------------------------------------------- |
| **언어**         | **Python (FastAPI)**  | 복잡한 금융 로직 처리 및 빠른 API 개발        |
| **데이터베이스** | **PostgreSQL**        | 금융 원장의 **ACID** 특성 보장 및 정합성 관리 |
| **블록체인**     | **Web3.py & Sepolia** | 온체인 상호작용 및 테스트넷 환경 구축         |
| **암호화**       | **PyCryptodome**      | MPC(Shamir's Secret Sharing) 논리 시뮬레이션  |
| **인프라**       | **Docker**            | Multi-Region 및 HSM 노드 환경 모사            |

---

## 🚀 3. Build Phase (Roadmap)

### Phase 1: 관제 센터 기반 구축 (The Gatekeeper)

- [ ] **PostgreSQL 원장 설계**: `Ledger`, `Transaction`, `Whitelist` 테이블 구축.
- [ ] **Policy Engine**: `Allow / Challenge / Block` 상태를 반환하는 정책 로직 구현.
- [ ] **Withdrawal API**: 출금 요청 접수 및 정책 검증 파이프라인 완성.

### Phase 2: MPC 분산 서명 시스템 (The Orchestrator)

- [ ] **Key Sharding**: 비밀키를 3개의 Share로 분할하여 저장하는 로직 구현.
- [ ] **Signing Protocol**: 2개 이상의 Share가 활성화될 때만 서명을 생성하는 워크플로우.
- [ ] **Broadcast Gateway**: 서명된 트랜잭션을 블록체인 네트워크로 전송.

### Phase 3: 실시간 감사 및 복구 (The Auditor)

- [ ] **On-Chain Indexer**: 블록체인 이벤트를 감시하여 거래 상태를 수집.
- [ ] **Reconciliation Service**: 원장과 온체인 결과 대조 후 상태 확정(`SETTLED`).
- [ ] **Break-Glass 모듈**: 비상용 Share(#3)를 이용한 복구 프로세스 코드화.

---

## 🧪 4. Test Scenarios (Testing Script)

시스템의 신뢰성을 증명하기 위해 다음 시나리오를 코드로 검증합니다.

### 4.1 정책 위반 차단 (Policy Test)

```python
# 미승인 주소 출금 시도 시 즉시 차단 여부 확인
def test_unauthorized_withdrawal_blocked():
    request = {"to": "BLACK_LIST_ADDR", "amount": 10.0}
    response = policy_engine.evaluate(request)
    assert response.status == "BLOCK" #
```

### 4.2 분산 가용성 검증 (MPC Test)

```python
# 1개 노드 장애 상황에서도 2개의 Share로 서명 가능 여부 확인
def test_mpc_threshold_with_one_failure():
active_shares = [share_1, share_2] # share_3은 오프라인
signature = mpc_orchestrator.sign(tx_data, active_shares)
assert signature is not None #
```

### 4.3 데이터 정합성 확인 (Reconciliation Test)

```python
# 온체인 실패 시 내부 원장이 롤백되는지 확인
def test_reconciliation_on_chain_failure():
    on_chain_result = "FAILED"
    reconciler.sync(tx_id, on_chain_result)
    assert ledger.get_status(tx_id) == "FAILED" #
```
