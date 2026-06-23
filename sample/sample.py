import http.server 
import random
import time
from prometheus_client import start_http_server 
from prometheus_client import Counter 
from prometheus_client import Gauge 
from prometheus_client import Summary 


# > 간단한 REST API 정의 

# 메트릭 객체 정의 
### 1. 카운팅 객체 
REQUESTS = Counter("hello_worlds_total", "Hello Worlds requested.!!")

### 2. 카운팅 예외 처리 객체 
EXCEPTIONS = Counter("hello_world_exceptions_total", "Exceptions serving Hello World.")

### 3. 판매량 카운팅 객체
SALES = Counter("hello_world_sales_krw_total", "원화 기준 Hello World 판매액")

### 4. 게이지 측정 객체 1
INPROGRESS = Gauge("hello_worlds_inprogress", "Number of Hello Worlds in progress")

### 5. 게이지 측정 객체 2
LAST = Gauge("hello_world_last_time_seconds", "The last time a Hello World was served.")
TIME = Gauge("time_seconds", "The current time.")
TIME.set_function(lambda: time.time())

### 6. 시스템 성능 관측 객체 
LATENCY = Summary("hello_world_latency_seconds", "Time for a request Hello World!!.")

class MyHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):

        start = time.time()

        # 진행중인 호출 개수 수집 
        INPROGRESS.inc()

        # 카운팅 지표 수집 + 1
        REQUESTS.inc() 

        # 예외 처리 지표 수집 + 1 
        with EXCEPTIONS.count_exceptions():
            if random.random() < 0.2:
                raise Exception
            
        # 원화로 표시된 판매량 추적
        won = random.random()
        SALES.inc(won)

        # 응답 데이터 
        body = b"<!doctype html><html><body><h1>Hello World</h1><p><a href='http://localhost:8000/metrics'>metrics</a></p></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        try:
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass

        # 마지막 호출이 완료된 시기 추적 
        LAST.set(time.time())
        INPROGRESS.dec()
        LATENCY.observe(time.time() - start)

if __name__ == "__main__":
    start_http_server(8000)

    server = http.server.HTTPServer(('127.0.0.1', 8081), MyHandler)
    print("listening: http://127.0.0.1:8081  |  metrics: http://127.0.0.1:8000/metrics")
    server.serve_forever()