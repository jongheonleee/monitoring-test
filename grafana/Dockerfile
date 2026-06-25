# 베이스는 공식 Grafana 최신 안정판
FROM grafana/grafana:latest

# provisioning 파일(데이터소스/대시보드 설정) 베이크
COPY provisioning /etc/grafana/provisioning

# 사전 정의 대시보드 JSON 베이크
COPY dashboards /var/lib/grafana/dashboards

# 컨테이너 3000 포트에서 듣음
EXPOSE 3000
