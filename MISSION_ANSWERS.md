# Day 14 Lab — Mission Answers

## Part 1 — Localhost vs Production

### Exercise 1.1 — Các vấn đề trong bản develop

| Vấn đề | Vị trí | Ảnh hưởng khi triển khai |
| --- | --- | --- |
| Ghi API key mẫu và URL cơ sở dữ liệu kèm mật khẩu ngay trong mã | [Dòng 17–18](01-localhost-vs-production/develop/app.py#L17-L18) | Nếu áp dụng cách này với credential thật, người có quyền đọc repo hoặc image có thể lấy được chúng. Việc đổi credential cũng đòi hỏi cập nhật mã và triển khai lại. |
| Đặt cấu hình ứng dụng bằng giá trị cố định | [Dòng 21–22](01-localhost-vs-production/develop/app.py#L21-L22) | Giá trị debug và giới hạn token nằm trực tiếp trong mã. Các môi trường cần cấu hình khác nhau sẽ khó dùng chung một bản build. |
| Dùng `print()` để ghi toàn bộ câu hỏi, câu trả lời và cả key | [Dòng 33–38](01-localhost-vs-production/develop/app.py#L33-L38) | Dữ liệu người dùng và credential có thể lọt vào hệ thống thu thập log. Log dạng văn bản tự do cũng khó lọc theo sự kiện. |
| Thiếu endpoint health và readiness | [Các route được khai báo](01-localhost-vs-production/develop/app.py#L25-L43) | Nền tảng thiếu tín hiệu riêng về việc tiến trình còn sống và việc instance đã sẵn sàng nhận traffic. |
| Bind vào `localhost` và cố định cổng `8000` | [Dòng 51–52](01-localhost-vs-production/develop/app.py#L51-L52) | Ứng dụng chỉ nhận kết nối qua loopback và có thể xung đột nếu cổng đã được dùng, hoặc không khớp cổng do môi trường deploy cấp. |
| Luôn bật `reload=True` | [Dòng 53](01-localhost-vs-production/develop/app.py#L53) | Tiến trình theo dõi file phục vụ lúc phát triển. Khi file thay đổi, server có thể khởi động lại ngoài kế hoạch. |
| Thiếu bước dọn tài nguyên của ứng dụng khi shutdown | [Cấu hình FastAPI và Uvicorn](01-localhost-vs-production/develop/app.py#L13) | Ứng dụng thiếu chỗ riêng để cập nhật trạng thái sẵn sàng và đóng các kết nối khi tiến trình dừng. |

### Exercise 1.2 — Kết quả gọi bản develop

Bản develop được kiểm tra trong Ubuntu WSL trên cổng tạm `41067`. Request dùng query parameter `question`.

```text
POST http://127.0.0.1:41067/ask?question=Hello
HTTP/1.1 200 OK
content-type: application/json
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 1.3 — So sánh với bản production

| Tính năng | Develop | Production | Vì sao quan trọng |
| --- | --- | --- | --- |
| Cấu hình và credential | Cố định host, port và credential mẫu trong mã. | `Settings` đọc `HOST`, `PORT`, `DEBUG` và key từ biến môi trường. | Cùng một bản build có thể chạy ở nhiều môi trường, với cấu hình và credential riêng. [Config](01-localhost-vs-production/production/config.py#L14-L34) |
| Logging | `print()` câu hỏi, key và câu trả lời. | Request và response có sự kiện JSON với độ dài câu hỏi hoặc câu trả lời. | Trường cố định dễ tìm kiếm, đồng thời giảm lượng dữ liệu nhạy cảm đi vào log. [Request logging](01-localhost-vs-production/production/app.py#L111-L122) |
| Liveness | Có route `/`. | `/health` trả trạng thái, phiên bản và uptime. | Nền tảng có endpoint riêng để xác nhận ứng dụng còn phản hồi. [Health](01-localhost-vs-production/production/app.py#L135-L149) |
| Readiness | Chưa có endpoint readiness. | `/ready` kiểm tra cờ được cập nhật trong lifespan và trả `503` khi chưa sẵn sàng. | Load balancer có thể chờ instance sẵn sàng trước khi chuyển traffic đến. [Readiness](01-localhost-vs-production/production/app.py#L152-L160) |
| Shutdown | Dựa vào hành vi mặc định của Uvicorn. | Lifespan cập nhật trạng thái readiness và ghi log trong giai đoạn shutdown. | Lifecycle là nơi ứng dụng có thể dọn tài nguyên khi server kết thúc. Uvicorn quản lý việc chờ các request đang xử lý. [Lifespan](01-localhost-vs-production/production/app.py#L39-L65) |
| Khởi động | Bind `localhost:8000` và luôn bật reload. | Host và cổng lấy từ `Settings`. Reload theo `DEBUG`. | Container có thể lắng nghe trên cổng được cấp, với reload tắt mặc định. [Khởi động Uvicorn](01-localhost-vs-production/production/app.py#L192-L199) |

Khi kiểm tra bản production đang chạy ở cổng `8000`, cả ba request dưới đây đều trả `200 OK`. `/ask` nhận body JSON và trả câu trả lời từ mock LLM.

| Request | HTTP | Kết quả quan sát |
| --- | --- | --- |
| `GET /health` | `200 OK` | `status` là `ok`, `version` là `1.0.0`. |
| `GET /ready` | `200 OK` | `{"ready":true}` |
| `POST /ask` với `{"question":"Docker la gi?"}` | `200 OK` | `answer` là `Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!` |

## Part 2 — Docker

### Exercise 2.1 — Dockerfile cơ bản

1. `FROM python:3.11` chọn image Python 3.11 làm base.
2. `WORKDIR /app` đặt thư mục làm việc bên trong container.
3. Dockerfile copy `requirements.txt` và cài dependencies trước khi copy mã ứng dụng. Nếu chỉ sửa `app.py`, lớp cài dependencies có thể được lấy lại từ cache khi build.
4. `CMD` đặt lệnh mặc định hoặc tham số mặc định khi container khởi động. `ENTRYPOINT` đặt chương trình chính. Khi có cả hai, `CMD` thường cung cấp tham số mặc định cho `ENTRYPOINT`. Dockerfile này dùng `CMD ["python", "app.py"]`.

[Dockerfile bản develop](02-docker/develop/Dockerfile)

### Exercise 2.2 — Chạy container

Container `my-agent:develop` nhận request qua cổng `8001` của máy. Kết quả từ terminal WSL:

```text
$ curl -i -X POST 'http://127.0.0.1:8001/ask?question=Hello'
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 2.3 — So sánh kích thước image

Kết quả đo bằng `docker image ls my-agent`:

| Image | Image ID | Disk usage | Content size |
| --- | --- | --- | --- |
| `my-agent:develop` | `627ce9f7aad0` | 1,67 GB | 426 MB |
| `my-agent:advanced` | `6998d29f507e` | 240 MB | 57,4 MB |

So theo cột **Content size**, bản advanced giảm khoảng **86,5%** (`100 × (426 − 57,4) / 426`). So theo cột **Disk usage**, mức giảm khoảng **85,6%** sau khi quy đổi 1,67 GB thành khoảng 1.670 MB. Hai tỷ lệ dùng số đã làm tròn mà Docker hiển thị.

Stage `builder` cài dependencies. Stage `runtime` bắt đầu từ image slim mới, copy packages đã cài và mã cần chạy, giúp loại build tool khỏi image cuối. [Dockerfile bản production](02-docker/production/Dockerfile)

### Exercise 2.4 — Compose và Nginx

```text
Client → Nginx → Agent
                   ├─ Redis
                   └─ Qdrant
```

Compose khai báo Redis và Qdrant trong mạng nội bộ, truyền địa chỉ hai service vào cấu hình agent và chờ health check của chúng. Client gọi Nginx trên cổng 80. Cả hai request thử đều có header `Server: nginx` và trả `200 OK`. [Compose Part 2](02-docker/production/docker-compose.yml)

```text
$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json

{"status":"ok","uptime_seconds":24.4,"version":"2.0.0","timestamp":"2026-11-25T09:26:01.784188"}

$ curl -i http://localhost/ask -H 'Content-Type: application/json' -d '{"question":"Hello"}'
HTTP/1.1 200 OK
Server: nginx
Content-Type: application/json

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

## Part 3 — Cloud Deployment

### Exercise 3.1 — Deploy trên Railway

Tôi triển khai agent Part 6 lên Railway, dùng Dockerfile trong thư mục `/06-lab-complete` và đặt health check `/health` trong dashboard. Railway báo `Healthcheck succeeded!`. Kiểm tra qua domain public từ Ubuntu WSL xác nhận `GET /health → 200`, `GET /ready → 200`, `POST /ask` thiếu API key → `401` và `POST /ask` với API key hợp lệ → `200`. Kết quả `/ready` xác nhận agent kết nối được Redis tại thời điểm kiểm tra. [URL public](https://day14-agent-production-49fc9e3e.up.railway.app) · [Các lệnh kiểm tra](DEPLOYMENT.md) · [Dashboard Railway](screenshots/dashboard.png) · [Deployment Active](screenshots/running.png) · [Ảnh kết quả HTTP](screenshots/test.png)

### Exercise 3.2 — So sánh Railway và Render

| Hạng mục | Railway | Render |
| --- | --- | --- |
| Phạm vi cấu hình | `railway.toml` dùng các mục `[build]` và `[deploy]` cho service agent. | `render.yaml` dùng Blueprint với danh sách `services`, có thể khai báo web service và kho dữ liệu cùng một file. |
| Build và khởi động | Mẫu Part 3 dùng `NIXPACKS` và `startCommand`. Agent Part 6 chọn `DOCKERFILE` để dùng đúng image đã kiểm thử. | Mẫu Part 3 dùng `runtime: python`, `buildCommand` và `startCommand`. Với Dockerfile của Part 6, web service có thể dùng `runtime: docker`. |
| Health check và secret | `healthcheckPath` đặt `/health`. Biến môi trường được cấu hình ở cấp service trên nền tảng. | `healthCheckPath` cũng đặt `/health`. Blueprint dùng `sync: false` để điền secret khi thiết lập hoặc `generateValue: true` để nền tảng tạo giá trị. |

Chọn Railway cho agent Part 6 vì cấu hình service có thể dùng trực tiếp Dockerfile đã kiểm thử. Redis được cung cấp riêng và agent dùng địa chỉ kết nối qua biến môi trường. [Mẫu Railway](03-cloud-deployment/railway/railway.toml) · [Mẫu Render](03-cloud-deployment/render/render.yaml)

### Exercise 3.3 — Pipeline Cloud Run

1. Bước `test` dùng image Python để cài dependencies và gọi `pytest tests/`.
2. Bước `build` chạy sau `test`, dùng Dockerfile để tạo image với tag theo commit SHA và tag `latest`.
3. Bước `push` đưa hai tag lên registry. Bước `deploy` dùng đúng tag commit SHA khi gọi `gcloud run deploy`.
4. `service.yaml` mô tả cấu hình chạy, gồm số instance tối thiểu/tối đa, giới hạn concurrency, tài nguyên, liveness/startup probe và secret lấy từ Secret Manager.

[Cloud Build pipeline](03-cloud-deployment/production-cloud-run/cloudbuild.yaml) · [Cloud Run service](03-cloud-deployment/production-cloud-run/service.yaml)

## Part 4 — API Security

### Exercise 4.1 — Xác thực bằng API key

Trong bản develop ở cổng `8002`, tôi gọi `POST /ask` với JSON `{"question":"Hello"}`. Khi thiếu `X-API-Key`, server yêu cầu gửi header xác thực:

```text
HTTP/1.1 401 Unauthorized
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

Khi gửi cùng câu hỏi với `X-API-Key` đúng, server trả lời:

```text
HTTP/1.1 200 OK
content-type: application/json

{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2 — Xác thực bằng JWT

Trong bản production, `POST /auth/token` đổi thông tin đăng nhập của tài khoản mẫu `student` lấy `access_token`. Client gửi `Authorization: Bearer <TOKEN>` khi gọi `POST /ask`. Lần kiểm tra bổ sung xác nhận `token_type=bearer`, `expires_in_minutes=60` và `POST /ask` trả `200 OK` với token hợp lệ. Server kiểm tra chữ ký và hạn dùng của JWT trước khi thực hiện logic xử lý câu hỏi. [Cấp token](04-api-gateway/production/app.py#L105-L117) · [Kiểm tra token](04-api-gateway/production/auth.py#L35-L67)

### Exercise 4.3 — Giới hạn request

Vòng lặp gửi 12 request với cùng tài khoản `student`. Request số **11** và **12** đều trả `429 Too Many Requests`. Trích output của request 11:

```text
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
content-type: application/json

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Limiter dùng **sliding window** 60 giây theo username. Mỗi lần gọi, nó bỏ các timestamp cũ, đếm request còn trong cửa sổ và chỉ thêm timestamp mới nếu còn lượt. `student` có **10 request/60 giây** và vai trò `admin` có limiter riêng **100 request/60 giây**. `Retry-After: 59` chỉ thời gian chờ tính bằng giây ở lần thử này. Bản mẫu giữ dữ liệu trong RAM của tiến trình, nên Part 6 cần lưu hạn mức trong Redis để nhiều worker dùng chung. [Thuật toán và hạn mức](04-api-gateway/production/rate_limiter.py#L17-L87) · [Chọn limiter theo vai trò](04-api-gateway/production/app.py#L137-L145)

### Exercise 4.4 — Cost guard

Bản mẫu gọi `check_budget()` trước khi gọi mock LLM. Nó so tổng chi phí với ngưỡng cấu hình **1 USD/ngày cho mỗi tài khoản** và **10 USD** cho toàn ứng dụng. Nếu chạm ngưỡng tài khoản, app trả `402`. Khi chạm ngưỡng toàn ứng dụng, bản mẫu trả `503`. Sau khi có câu trả lời, app ước lượng token đầu vào và đầu ra, nhân từng lượng token với đơn giá tương ứng rồi cộng vào tổng chi phí. [Luồng xử lý](04-api-gateway/production/app.py#L137-L153) · [Cost guard trong bản mẫu](04-api-gateway/production/cost_guard.py#L39-L109)

Với bài toán **10 USD mỗi người dùng mỗi tháng**, tôi sẽ dùng Redis key theo người dùng và tháng UTC, ví dụ `cost:student:2026-11`. Trước khi gọi LLM, kiểm tra tổng đã chi cộng chi phí ước tính có vượt 10 USD hay không. Sau khi hoàn thành, cộng chi phí thực vào Redis. Tháng mới dùng key mới, còn key cũ có thể hết hạn sau thời gian lưu báo cáo. Nếu nhiều request có thể chạy đồng thời, cần giữ chỗ ngân sách bằng thao tác nguyên tử trước khi gọi LLM rồi điều chỉnh theo chi phí thực khi xong.

Rate limit kiểm soát **tần suất** gọi, còn cost guard kiểm soát **chi phí theo token**. Một request với nhiều token có thể tốn nhiều tiền dù người dùng vẫn còn lượt gọi.

## Part 5 — Scaling & Reliability

### Exercise 5.1 — Liveness và readiness

- `GET /health` là liveness probe. Nó cho biết tiến trình còn phản hồi và trong bản develop có kèm trạng thái, uptime và kiểm tra bộ nhớ.
- `GET /ready` là readiness probe. Bản develop trả `503` khi cờ sẵn sàng chưa bật và `200` khi đã khởi động xong. Trong bản production của Part 5, `/ready` còn kiểm tra kết nối Redis. Load balancer có thể dùng tín hiệu này để ngừng chuyển traffic đến instance chưa sẵn sàng.

Kiểm tra bổ sung bản develop trên một cổng tạm trong Ubuntu WSL cho kết quả `GET /health → 200` với `status: ok` và `GET /ready → 200` với `ready: true`. [Probe bản develop](05-scaling-reliability/develop/app.py#L104-L168) · [Readiness bản production](05-scaling-reliability/production/app.py#L208-L215)

### Exercise 5.2 — Graceful shutdown

Tôi gửi `POST /ask?question=Hello` trên cổng `8003`, sau đó gửi `SIGTERM` trong lúc request đang xử lý. Log cho thấy request hoàn tất với `200 OK` và Uvicorn đi qua giai đoạn shutdown:

```text
INFO:     Shutting down
INFO:     127.0.0.1:35100 - "POST /ask?question=Hello HTTP/1.1" 200 OK
HTTP/1.1 200 OK
INFO:     Waiting for application shutdown.
Graceful shutdown initiated...
Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [2597]
```

Kết quả cho thấy request đang chạy vẫn được phục vụ trước khi tiến trình kết thúc. Trong bản mẫu, FastAPI lifespan cập nhật trạng thái sẵn sàng khi ứng dụng chuyển sang giai đoạn shutdown. [Lifespan bản develop](05-scaling-reliability/develop/app.py#L41-L67)

### Exercise 5.3 — Stateless với Redis

Mỗi tiến trình có bộ nhớ riêng. Nếu instance A giữ session trong RAM của nó, request tiếp theo đến instance B sẽ thiếu lịch sử. Trong bản production, các instance đọc và ghi history theo cùng `session_id` trong Redis. Mỗi lượt thêm một tin nhắn `user` và một tin nhắn `assistant`, nên instance nào cũng đọc được lịch sử chung. [Lưu session và history](05-scaling-reliability/production/app.py#L59-L90) · [Xử lý `/chat`](05-scaling-reliability/production/app.py#L128-L169)

### Exercise 5.4–5.5 — Load balancing và kiểm tra session

Tôi chạy stack `k5-day14-scaling` với 3 replica và gửi 5 request qua Nginx ở cổng `8080` bằng `python test_stateless.py`. Các request dùng cùng một session. Kết quả `served_by` trong lần chạy:

| Request | Instance phục vụ |
| --- | --- |
| 1 | `instance-83ca16` |
| 2 | `instance-47499c` |
| 3 | `instance-29583c` |
| 4 | `instance-83ca16` |
| 5 | `instance-47499c` |

```text
Total requests: 5
Instances used: {'instance-47499c', 'instance-83ca16', 'instance-29583c'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

Cả ba instance đều phục vụ request. Khi đọc lại session, history có đủ 5 câu hỏi và 5 câu trả lời theo thứ tự. Kết quả xác nhận session được chia sẻ giữa các instance trong lần chạy. Script kiểm tra việc phân phối request và giữ lịch sử trên stack đang chạy. [Nginx upstream](05-scaling-reliability/production/nginx.conf) · [Script kiểm tra](05-scaling-reliability/production/test_stateless.py)

## Part 6 — Production Readiness Check

Kết quả dưới đây lấy từ lần chạy đầy đủ `python check_production_ready.py` trong Ubuntu WSL với Docker, tại thư mục `06-lab-complete/`.

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

- Image multi-stage đo được **273 MB**. Container khởi động được khi chạy riêng và `/health` trả `200`.
- Khi Redis không kết nối được, `/health` vẫn trả `200` vì tiến trình còn hoạt động, còn `/ready` trả `503` vì agent cần Redis để áp dụng rate limit và cost guard.
- Bộ chấm thấy `429` sau 5 request thành công với hạn mức thử nghiệm. Sau khi restart agent, hạn mức vẫn được giữ trong Redis. Bộ chấm cũng quan sát `402` khi hết ngân sách thử nghiệm.
- Request đang xử lý vẫn trả `200` sau SIGTERM và process thoát với mã `0`. Trong Docker, `docker stop` hoàn tất sau **1,3 giây** với mã thoát `0`.
- Kiểm tra bổ sung trên Docker Compose gửi 12 request đồng thời với hạn mức 5. Có đúng 5 phản hồi `200` và 7 phản hồi `429` kèm `Retry-After`. Request thiếu `question` trả `422`. Khi dừng Redis trong stack thử nghiệm, `/health` vẫn trả `200` và `/ready` trả `503`.

Agent dùng sliding window Redis theo API key và ghi tổng chi phí vào Redis theo ngày UTC. API key được đọc từ môi trường. Log ứng dụng là JSON, ghi mã HTTP và thời lượng. FastAPI lifespan đóng Redis client trong lúc shutdown. [Agent Part 6](06-lab-complete/app/main.py) · [Rate limit](06-lab-complete/app/rate_limiter.py) · [Cost guard](06-lab-complete/app/cost_guard.py)

## AI log

- Tôi dùng Codex để đọc yêu cầu lab, đối chiếu mã nguồn hai bản app và soạn câu trả lời CP1. Codex chạy thử bản develop trong WSL trên một cổng tạm và gọi các endpoint của bản production đang chạy ở cổng 8000. Phần kết quả CP1 ghi từ các phản hồi HTTP đó.
- Tôi dùng Codex để giải thích Dockerfile và tính tỷ lệ giảm kích thước image. Tôi tự build hai image, chạy `docker image ls my-agent` và gọi API trên container và qua Nginx. Codex ghi lại số đo và phản hồi HTTP từ ảnh terminal tôi gửi.
- Tôi dùng Codex để đối chiếu bản mẫu xác thực, rate limit và cost guard trong CP3. Tôi tự chạy các lệnh `curl` và quan sát mã `401`, `200`, `429`. Codex ghi lại kết quả từ ảnh, kiểm tra bổ sung JWT trên bản local và giải thích cách lưu ngân sách theo tháng trong Redis.
- Tôi dùng Codex để tóm tắt kết quả CP4. Tôi tự gửi SIGTERM trong lúc có request và chạy `test_stateless.py` với ba replica. Codex ghi lại bằng chứng tôi gửi, đối chiếu cách Nginx và Redis được sử dụng, và gọi bổ sung `/health` cùng `/ready` trên bản develop trong WSL.
- Tôi nhờ Codex triển khai các TODO của agent CP5 và cập nhật mục cloud trong file này. Codex chọn Railway cho cấu hình deploy và dùng ngân sách theo ngày UTC. Codex chạy nguyên script chấm trong WSL với Docker, ghi lại `PASS 12/12`, rồi kiểm tra bổ sung Docker Compose với 12 request đồng thời và thử dừng Redis.
- Tôi dùng Codex để đọc log lỗi Root Directory trên Railway và hướng dẫn kiểm tra CP6. Tôi chạy deployment trên Railway và cung cấp log health check cùng domain public. Codex kiểm tra ba request công khai trong WSL và ghi kết quả thật vào `DEPLOYMENT.md`.
- Tôi nhờ Codex chạy đủ bốn kiểm tra CP6, gồm request có API key. Codex ghi nhận `200, 200, 401, 200` từ domain Railway và xuất kết quả HTTP trong WSL thành `screenshots/test.png`.
- Tôi nhờ Codex thực hiện CP7. Codex thêm histogram độ dài câu hỏi, chạy load test và eval local trong WSL, bổ sung hai tài liệu JWT và HPA dựa trên lỗi của baseline, rồi kiểm tra lại. [Báo cáo CP7](BENCHMARK_REPORT.md) dùng kết quả đã lưu trong `reports/`.
- Tôi nhờ Codex hoàn thiện CP8. Codex sửa Dockerfile observability để đường dẫn home của user khớp thư mục cài dependencies, rồi xác minh 1 và 3 replica trong hai lượt Locust. Codex chạy hai thí nghiệm lỗi, kiểm tra alert rules, đối chiếu `trace_id` với log JSON và lưu ảnh thật của stack local. [Báo cáo CP8](BENCHMARK_REPORT.md#4-observability-stack-production-cp8)
