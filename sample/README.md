# sample.py 실행 방법

`prometheus_client` 라이브러리를 사용하는 간단한 HTTP 서버 예제.

- `http://localhost:8000/metrics` — Prometheus 메트릭 엔드포인트
- `http://localhost:8081/` — "Heloo World" 응답

## 사전 준비

프로젝트 루트(`c:\Users\qwefg\Mywork\awasoft\prometheus`)에서 venv 생성 및 의존성 설치:

```powershell
python -m venv .venv
& ".venv\Scripts\python.exe" -m pip install prometheus_client
```

## 실행

프로젝트 루트에서:

```powershell
& ".venv\Scripts\python.exe" sample\sample.py
```

또는 venv 활성화 후:

```powershell
& ".venv\Scripts\Activate.ps1"
python sample\sample.py
```

종료는 `Ctrl+C`.

## 동작 확인

서버 띄운 상태에서 다른 터미널:

```powershell
Invoke-WebRequest http://localhost:8081/ -UseBasicParsing
Invoke-WebRequest http://localhost:8000/metrics -UseBasicParsing
```
