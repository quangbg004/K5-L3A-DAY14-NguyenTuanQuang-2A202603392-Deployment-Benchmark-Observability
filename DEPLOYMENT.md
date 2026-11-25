# Day 14 — Deployment

## URL công khai

[Agent trên Railway](https://day14-agent-production-49fc9e3e.up.railway.app)

## Cấu hình triển khai

- Nền tảng Railway, service `day14-agent`.
- Thư mục nguồn `/06-lab-complete`, với Dockerfile multi-stage và health check `/health`.
- Agent dùng `REDIS_URL` để kết nối Redis và `AGENT_API_KEY` để xác thực client.
- Các biến cấu hình khác của agent gồm `ENVIRONMENT`, `PORT`, `RATE_LIMIT_PER_MINUTE` và `DAILY_BUDGET_USD`.

## Kiểm tra từ terminal Ubuntu

```bash
BASE='https://day14-agent-production-49fc9e3e.up.railway.app'
read -rsp 'AGENT_API_KEY: ' AGENT_API_KEY
printf '\nURL kiểm tra: %s\n' "$BASE"

curl -sS -o /dev/null -w 'GET /health: %{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w 'GET /ready: %{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w 'POST /ask thiếu key: %{http_code}\n' \
  "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w 'POST /ask có key: %{http_code}\n' \
  "$BASE/ask" -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

| Kiểm tra | Kết quả đã quan sát |
| --- | --- |
| `GET /health` | `200`, `{"status":"ok"}` |
| `GET /ready` | `200`, `{"ready":true}` |
| `POST /ask` thiếu API key | `401`, `{"detail":"Missing or invalid API key"}` |
| `POST /ask` với API key hợp lệ | `200` |

## Ảnh CP6

- [dashboard.png](screenshots/dashboard.png) — trang Projects của Railway cho thấy project `perfect-rebirth`, environment `production` và `2/2 services online`.
- [running.png](screenshots/running.png) — deployment `Complete Day 14 production agent` có trạng thái `ACTIVE` và thông báo `Deployment successful`.
- [test.png](screenshots/test.png) — ảnh xuất từ kết quả HTTP thực tế trong Ubuntu WSL, gồm URL public và cả bốn mã HTTP.
