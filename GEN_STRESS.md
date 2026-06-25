
# GEN_STRESS.md — 부하 생성 명령어 모음

각 샘플 앱에 다양한 패턴의 트래픽을 쏴서 Prometheus 메트릭이 어떻게 변하는지 관찰하기 위한 명령어 모음. PowerShell 기준.

---

## 대상 엔드포인트 요약

| 샘플 | 핸들러 (트래픽 받음) | 메트릭 (Prometheus가 긁어감) | 비고 |
|---|---|---|---|
| sample.py | `http://127.0.0.1:8081/*` | `http://127.0.0.1:8000/metrics` | 20% 확률로 예외 발생 |
| sample3.py | `http://localhost:8000/` | `http://localhost:8000/metrics` | sample.py와 8000 충돌 — 동시에 띄울 수 없음 |
| sample4.py | `http://localhost:8001/*` | `http://localhost:8002/metrics` | path가 그대로 라벨로 들어감 |
| sample5.py | (외부 트래픽 불필요) | `http://localhost:8003/metrics` | 백그라운드 자체 루프 |
| sample6.py | (외부 트래픽 불필요) | `http://localhost:8004/metrics` | 백그라운드 상태머신 |

부하는 sample.py / sample3.py / sample4.py 에만 의미가 있음.

---

## 0. 공통 헬퍼 — 메트릭 직접 보기

```powershell
# sample4 메트릭만 확인
(Invoke-WebRequest http://localhost:8002/metrics -UseBasicParsing).Content | Select-String hello_worlds_total

# 4개 샘플 메트릭 한 번에 확인
8000,8002,8003,8004 | ForEach-Object {
    Write-Host "===== port $_ =====" -ForegroundColor Cyan
    try { (Invoke-WebRequest "http://localhost:$_/metrics" -UseBasicParsing -TimeoutSec 2).Content | Select-String "_total$|gauge|^# HELP" | Select-Object -First 10 }
    catch { Write-Host "down" -ForegroundColor Red }
}
```

---

## 1. sample.py — 기본 카운터/게이지/Summary 부하

엔드포인트: `http://127.0.0.1:8081/`. path는 무시되지만 20% 확률로 예외 발생함 → `hello_world_exceptions_total` 관측 가능.

### 1-1. 가벼운 직선 부하 (30회)

```powershell
1..30 | ForEach-Object {
    Invoke-WebRequest "http://127.0.0.1:8081/" -UseBasicParsing | Out-Null
    Start-Sleep -Milliseconds 300
}
Write-Host "Done"
```

관찰: `hello_worlds_total`, `hello_world_exceptions_total` (약 6개 예외 기대), `hello_world_sales_krw_total`.

### 1-2. 빠른 버스트 (100회 즉시)

```powershell
1..100 | ForEach-Object {
    try { Invoke-WebRequest "http://127.0.0.1:8081/" -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {}
}
Write-Host "Burst done"
```

관찰: PromQL `rate(hello_worlds_total[1m])` 그래프에 스파이크.

### 1-3. 장기 백그라운드 트래픽 (1시간)

```powershell
Start-Job -Name LongHello -ScriptBlock {
    $end = (Get-Date).AddHours(1)
    while ((Get-Date) -lt $end) {
        try { Invoke-WebRequest "http://127.0.0.1:8081/" -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {}
        Start-Sleep -Milliseconds (Get-Random -Minimum 100 -Maximum 1500)
    }
}
# 멈추려면: Stop-Job LongHello; Remove-Job LongHello
```

관찰: 시간 흐름에 따른 카운터/Summary 변화. `rate()`로 분당 평균 속도.

### 1-4. 동시성 부하 (PowerShell 7+ 한정, `ForEach-Object -Parallel`)

```powershell
# pwsh (PowerShell 7+)에서만 동작
1..200 | ForEach-Object -Parallel {
    try { Invoke-WebRequest "http://127.0.0.1:8081/" -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {}
} -ThrottleLimit 20
```

관찰: `hello_worlds_inprogress` 게이지가 순간적으로 올라갔다가 내려옴.

### 1-5. 의도적 예외 폭증 (단순 반복으로 확률 기반 예외 누적)

```powershell
# 500회 → 약 100개 예외 기대 (20% rate)
1..500 | ForEach-Object {
    try { Invoke-WebRequest "http://127.0.0.1:8081/" -UseBasicParsing -TimeoutSec 2 | Out-Null } catch {}
}
```

PromQL: `rate(hello_world_exceptions_total[5m]) / rate(hello_worlds_total[5m])` → 예외율 약 0.2 수렴.

---

## 2. sample4.py — path 라벨 부하

핸들러는 `localhost:8001`. path가 통째로 `path` 라벨이 됨.

### 2-1. 다양한 path 랜덤 분포

```powershell
$paths = @("/foo","/bar","/baz","/api/users","/api/orders","/admin","/health","/metrics-fake")
1..50 | ForEach-Object {
    $p = $paths | Get-Random
    Invoke-WebRequest "http://localhost:8001$p" -UseBasicParsing | Out-Null
    Start-Sleep -Milliseconds 200
}
Write-Host "Done"
```

PromQL: `sum by (path) (hello_worlds_total)` → path별 누적.

### 2-2. path별 가중치 다르게 (Zipf 같은 편향)

```powershell
# 인기 path는 많이, 비인기 path는 적게
$weighted = @()
$weighted += ,"/api/users" * 50
$weighted += ,"/api/orders" * 30
$weighted += ,"/foo" * 15
$weighted += ,"/admin" * 5

1..100 | ForEach-Object {
    $p = $weighted | Get-Random
    Invoke-WebRequest "http://localhost:8001$p" -UseBasicParsing | Out-Null
    Start-Sleep -Milliseconds 100
}
```

PromQL: `topk(3, sum by (path) (hello_worlds_total))` → 상위 path 3개.

### 2-3. 쿼리스트링/긴 path (cardinality 폭증 주의 실험)

```powershell
# WARNING: 라벨 cardinality 폭증 사례 — 실제 운영에선 절대 금지
1..200 | ForEach-Object {
    $id = [guid]::NewGuid().ToString("N").Substring(0,8)
    Invoke-WebRequest "http://localhost:8001/user/$id" -UseBasicParsing | Out-Null
}
```

관찰: Prometheus가 시리즈 200개를 새로 만듦. `count(hello_worlds_total)` 로 확인 가능. **이게 라벨에 ID 박으면 안 되는 이유의 실증 데모**.

### 2-4. 일정한 RPS (초당 N건) — 정밀 부하

```powershell
$rps = 5
$duration = 60   # 초
$paths = @("/foo","/bar","/api/users","/api/orders","/admin")

$end = (Get-Date).AddSeconds($duration)
while ((Get-Date) -lt $end) {
    $start = Get-Date
    1..$rps | ForEach-Object {
        $p = $paths | Get-Random
        try { Invoke-WebRequest "http://localhost:8001$p" -UseBasicParsing -TimeoutSec 1 | Out-Null } catch {}
    }
    $elapsed = ((Get-Date) - $start).TotalMilliseconds
    if ($elapsed -lt 1000) { Start-Sleep -Milliseconds (1000 - $elapsed) }
}
Write-Host "RPS=$rps for ${duration}s done"
```

PromQL: `rate(hello_worlds_total[1m])` 합계가 약 `$rps` 근처 수렴해야 함.

### 2-5. 스파이크 패턴 (저 → 폭증 → 저)

```powershell
# 5초 잠잠 → 5초 폭증 → 5초 잠잠 반복 (총 3사이클)
1..3 | ForEach-Object {
    Write-Host "[low]" -ForegroundColor Green
    1..10 | ForEach-Object {
        Invoke-WebRequest "http://localhost:8001/foo" -UseBasicParsing | Out-Null
        Start-Sleep -Milliseconds 500
    }
    Write-Host "[SPIKE]" -ForegroundColor Yellow
    1..200 | ForEach-Object {
        try { Invoke-WebRequest "http://localhost:8001/foo" -UseBasicParsing -TimeoutSec 1 | Out-Null } catch {}
    }
}
```

PromQL Graph: `rate(hello_worlds_total[30s])` → 톱니바퀴 모양 그래프.

---

## 3. sample3.py — WSGI Hello World (가장 단순)

핸들러: `http://localhost:8000/`. 메트릭 라벨 없음, 기본 prometheus_client 메트릭만.

```powershell
1..100 | ForEach-Object {
    Invoke-WebRequest "http://localhost:8000/" -UseBasicParsing | Out-Null
    Start-Sleep -Milliseconds 100
}
```

볼 만한 것: `python_gc_*`, `process_resident_memory_bytes` 같은 기본 메트릭 변화.

---

## 4. 동시 다발 부하 — 여러 샘플 동시에

```powershell
# sample.py (8081), sample4.py (8001) 동시 부하 30초
$jobs = @()
$jobs += Start-Job -Name S1 -ScriptBlock {
    $end = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $end) {
        try { Invoke-WebRequest "http://127.0.0.1:8081/" -UseBasicParsing -TimeoutSec 1 | Out-Null } catch {}
        Start-Sleep -Milliseconds 200
    }
}
$jobs += Start-Job -Name S4 -ScriptBlock {
    $paths = @("/foo","/bar","/api/users","/api/orders","/admin")
    $end = (Get-Date).AddSeconds(30)
    while ((Get-Date) -lt $end) {
        $p = $paths | Get-Random
        try { Invoke-WebRequest "http://localhost:8001$p" -UseBasicParsing -TimeoutSec 1 | Out-Null } catch {}
        Start-Sleep -Milliseconds 150
    }
}
$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
Write-Host "All jobs done"
```

PromQL: `sum by (job) (rate({__name__=~"hello_worlds.*"}[1m]))` → 잡별 처리 속도.

---

## 5. 외부 도구 — `hey` (있으면 강력 추천)

PowerShell 루프는 느리고 부정확함. 진짜 부하 테스트는 [hey](https://github.com/rakyll/hey) 같은 전문 도구가 좋아.

```powershell
# 설치 (Go 필요) or release 바이너리 다운로드
# https://github.com/rakyll/hey/releases

# 동시 50, 총 1000 요청
hey -n 1000 -c 50 http://localhost:8001/api/users

# 30초 동안 RPS 100 유지
hey -z 30s -q 100 -c 10 http://localhost:8001/api/users

# 무작위 path 랜덤 분포는 hey가 직접 지원 안 하므로 path별로 따로 실행
hey -n 200 -c 10 http://localhost:8001/api/users
hey -n 200 -c 10 http://localhost:8001/api/orders
hey -n 200 -c 10 http://localhost:8001/admin
```

대안: `wrk`, `ab` (Apache Bench), `vegeta`.

---

## 6. PromQL 관찰 치트시트

부하 넣은 후 `http://localhost:19090` 에서 확인:

| 쿼리 | 무엇을 보는가 |
|---|---|
| `rate(hello_worlds_total[1m])` | path별 분당 평균 RPS |
| `sum(rate(hello_worlds_total[1m]))` | 전체 RPS |
| `topk(3, sum by (path) (hello_worlds_total))` | 상위 3 path |
| `rate(hello_world_exceptions_total[5m]) / rate(hello_worlds_total[5m])` | 예외율 |
| `hello_worlds_inprogress` | 현재 처리 중인 요청 수 |
| `histogram_quantile(0.95, rate(hello_world_latency_seconds_bucket[5m]))` | p95 지연 (Summary는 quantile 직접) |
| `count(hello_worlds_total)` | path 시리즈 카디널리티 (cardinality 폭증 체크) |
| `increase(hello_worlds_total[5m])` | 지난 5분 증가량 |

---

## 7. 정리 — 백그라운드 잡 / 좀비 프로세스 청소

```powershell
# 모든 PowerShell Job 정리
Get-Job | Stop-Job; Get-Job | Remove-Job

# 8001~8004, 8081 잡고 있는 프로세스 강제 종료
8000,8001,8002,8003,8004,8081 | ForEach-Object {
    Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
}

# venv의 python 다 죽이기 (확실하게)
Get-Process python -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "*\.venv\*" } |
    Stop-Process -Force
```

---

## 사용 팁

- 첫 실행: **1-1** (가벼운 직선) → **2-1** (path 다양화) 로 일단 데이터 채우기
- 그래프 보고 싶을 때: **2-5** (스파이크 패턴) → Prometheus Graph 탭에서 `rate(...[30s])` 확인
- cardinality 함정 체험: **2-3** 돌리고 `count(hello_worlds_total)` 가 폭증하는 거 보기
- 운영 비슷한 부하: **2-4** (일정 RPS) + **1-3** (장기 백그라운드) 조합
