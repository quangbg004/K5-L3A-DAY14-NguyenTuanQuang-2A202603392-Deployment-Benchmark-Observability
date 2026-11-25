# Benchmark & Observability Report — Day 14

- **Họ tên** Nguyễn Tuấn Quang
- **Ngày chạy** 25/11/2026, GMT+7
- **Môi trường** Ubuntu trên WSL2, Python 3.12.3, 8 CPU logic khả dụng và 7,7 GiB RAM trong WSL. Các agent mock chạy trên loopback.

## 1. SLO của agent

| SLI | Ngưỡng | Lý do |
| --- | --- | --- |
| p95 latency `/ask` | ≤ 500 ms | Giữ tốc độ phản hồi cho ít nhất 95% request thành công. Đây là ngưỡng mặc định của `load_test.py`. |
| Error rate `/ask` | ≤ 2% | Giới hạn tỷ lệ request thất bại trong mỗi lượt chạy. Đây là ngưỡng mặc định của `load_test.py`. |
| Accuracy sau khi sửa knowledge base | ≥ 100%, không có regression | Quality gate cuối của CP7 chạy trên bộ 23 câu cố định và đối chiếu với baseline v2. |

## 2. Benchmark hiệu năng

### 2.0 — Đọc metrics của agent

Sau một request `What is Docker?`, `/metrics` trên agent v2 trả các dòng sau:

```text
http_requests_total{method="POST",route="/ask",status="200"} 1.0
agent_in_flight_requests 0.0
agent_question_length_chars_bucket{le="20.0"} 1.0
agent_question_length_chars_count 1.0
agent_question_length_chars_sum 15.0
```

`http_requests_total` là counter đếm request. `agent_in_flight_requests` là gauge đo số request đang xử lý ở thời điểm scrape. `agent_question_length_chars` là histogram mới để đo phân bố độ dài câu hỏi. Request thử dài 15 ký tự và được ghi vào bucket tối đa 20 ký tự. Dùng route template như `/ask` và nhãn `unmatched` cho đường dẫn lạ giúp giới hạn số time series khi URL thay đổi. [Instrumentation](06-lab-complete/benchmark-observability/develop/app.py)

### 2.1 Concurrency và latency của agent v2

Mỗi lượt đo 300 request, dùng `mock-llm-small` với `MOCK_SLOW_RATE=0.03` và `MOCK_ERROR_RATE=0.01`. Các phép đo hiệu năng dùng bản v2 trước khi bổ sung hai mục knowledge base. RPS tính trên toàn bộ request đo được và percentile latency tính trên các phản hồi HTTP `200`. [Load test](06-lab-complete/benchmark-observability/develop/load_test.py)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [1](reports/load_v2_c1.json) | 4,20 | 188,4 | 220,2 | 1.695,8 | 0,33% | PASS |
| [10](reports/load_v2_c10.json) | 38,63 | 194,2 | 223,2 | 1.689,5 | 0,33% | PASS |
| [50](reports/load_v2_c50.json) | 110,68 | 203,4 | 297,9 | 1.713,5 | 1,67% | PASS |
| [100](reports/load_v2_c100.json) | 51,18 | 483,1 | 3.893,6 | 4.316,9 | 1,67% | FAIL p95 |

Throughput đạt mức cao nhất trong lần đo ở concurrency 50. Khi tăng lên 100, số request đồng thời tăng gấp đôi, RPS giảm từ 110,68 xuống 51,18 và p95 tăng từ 297,9 lên 3.893,6 ms. Error rate vẫn ở mức 1,67%. Test này đo HTTP end-to-end trên một máy, nơi server Uvicorn và chương trình phát tải dùng chung tài nguyên. Cần số liệu saturation của CP8 để xác định nguyên nhân cụ thể của mức giảm throughput.

### 2.2 Tail latency

Mỗi hàng đo 300 request với concurrency 20. App được khởi động lại khi đổi `MOCK_SLOW_RATE`. Tỷ lệ lỗi mô phỏng giữ ở `0.01` trong cả ba lượt.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
| --- | ---: | ---: | ---: | ---: | --- |
| [0](reports/load_v2_slow_0.json) | 196,3 | 231,2 | 246,0 | 2,33% | FAIL error rate |
| [0.03](reports/load_v2_slow_0.03.json) | 251,7 | 227,3 | 1.708,7 | 0,67% | PASS |
| [0.1](reports/load_v2_slow_0.1.json) | 318,3 | 1.683,9 | 1.709,7 | 1,33% | FAIL p95 |

Ở slow rate 3%, p99 tăng từ 246,0 lên 1.708,7 ms trong khi p95 vẫn dưới 500 ms. Ở slow rate 10%, số request chậm đủ nhiều để p95 lên 1.683,9 ms dù trung bình là 318,3 ms. p99 phát hiện đuôi chậm ngay ở mức 3%, còn p95 cho biết ảnh hưởng khi nhiều request rơi vào đuôi. Phép thử ở slow rate 0 vẫn có 7 lỗi mô phỏng `503` trên 300 request, nên vi phạm SLO error rate riêng.

## 3. Benchmark chất lượng

Các lượt eval dùng cùng golden dataset 23 câu, cùng model `mock-llm-small`, `MOCK_ERROR_RATE=0` và `MOCK_SLOW_RATE=0.03`. Một câu đạt khi câu trả lời chứa ít nhất 60% từ khóa kỳ vọng. Chi phí tính theo giá mock trong repo.

| Chỉ số | [Agent v1](reports/eval_v1.json) | [Agent v2](reports/eval_v2.json) | [Agent v2 sau khi sửa KB](reports/eval_v2_fixed.json) |
| --- | ---: | ---: | ---: |
| Accuracy | 4,3% (1/23) | 91,3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57,0 | 109,0 | 114,3 |
| Tổng cost (USD) | 0.000403 | 0.000760 | 0.000796 |
| Cost / câu đúng (USD) | 0.00040275 | 0.00003619 | 0.00003459 |
| p95 latency của lượt eval (ms) | 1.514,1 | 213,0 | 215,3 |
| Quality gate | FAIL ở ngưỡng 80% | PASS ở ngưỡng 80%, 0 regression so với v1 | PASS ở ngưỡng 100%, 0 regression so với v2 baseline |

| ID chưa đạt ở baseline v2 | Keyword bị thiếu | Thay đổi trong knowledge base |
| --- | --- | --- |
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm tài liệu retrieval cho JWT và phân biệt thông tin trong JWT với cách API key được cấp và kiểm tra. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm tài liệu retrieval cho HPA và các nhóm chỉ số có thể dùng để quyết định số replica. |

V2 đưa tài liệu truy xuất vào prompt nên dùng trung bình 109,0 token mỗi câu, so với 57,0 ở v1. Số câu đúng tăng từ 1 lên 21, giúp chi phí mỗi câu đúng giảm từ 0.00040275 xuống 0.00003619 USD. Hai tài liệu mới giúp sửa tiếp 2 câu và giảm chi phí mỗi câu đúng xuống 0.00003459 USD. Mẫu eval chỉ có 23 câu và vẫn có độ trễ mô phỏng ngẫu nhiên. Các kết luận về latency khi chịu tải dựa vào 300 request mỗi lượt ở mục 2.

### Quality gate trong CI

Job CI cài dependencies, khởi động agent v2 với `MOCK_ERROR_RATE=0`, chờ `/health` trả `200`, rồi chạy `eval/run_eval.py` với `--min-accuracy 1.0 --baseline ../../../reports/eval_v2.json` từ thư mục `develop/` và truyền URL của agent đang chạy. Nếu accuracy dưới ngưỡng hoặc có regression, script trả exit code `1`. Đặt job làm required check để trạng thái thất bại chặn merge. Tôi đã thử v1 với baseline v2 và ngưỡng 85%, kết quả script trả `1` với **20 regression**. [Script eval và exit code](06-lab-complete/benchmark-observability/develop/eval/run_eval.py)

## 4. Observability stack (production, CP8)

### 4.1 Dashboard Grafana

- [Grafana khi có tải](screenshots/grafana-dashboard.png) hiển thị traffic, error rate, latency p95, request đang xử lý và 3 instance.
- [Trace chậm](screenshots/jaeger-slow-trace.png) mở span `chat mock-llm-small` trong Jaeger.
- [Trace lỗi](screenshots/jaeger-error-trace.png) hiển thị phản hồi `503` và event `exception`.
- [Prometheus Alerts](screenshots/prometheus-alert-firing.png) cho thấy `AgentHighErrorRate` và `AgentInstanceDown` cùng `FIRING`.

Ở cuối lượt Locust 3 replica, Grafana hiển thị khoảng **62,6 req/s**, error rate **0,93%**, p95 **295,82 ms** và **14 request đang xử lý**. Mẫu PromQL gần cùng thời điểm cho avg **239,03 ms**, p95 **295,66 ms** và p99 **1.843,95 ms**. P99 cho thấy còn một nhóm request chậm hơn nhiều so với phần lớn traffic.

Ba instance nhận lần lượt **20,80**, **20,71** và **20,91 req/s** theo truy vấn `rate` trong 1 phút, nên lưu lượng trong mẫu gần như chia đều. Prometheus ghi nhận **4.570,05 input token/s** và **2.427,82 output token/s**. Prompt v2 chứa thêm tài liệu retrieval, làm tăng lượng token đầu vào. Gọi `/metrics` qua Nginx ở cổng 8080 trả `404` theo cấu hình proxy. Prometheus scrape endpoint này trực tiếp trên mỗi container. [Dashboard và truy vấn](06-lab-complete/benchmark-observability/production/grafana/dashboards/agent-overview.json) · [Cấu hình scrape](06-lab-complete/benchmark-observability/production/prometheus/prometheus.yml)

### 4.2 Thí nghiệm alert

Tôi dùng Locust với 30 users, ramp-up 5 users/giây. Thời gian tính từ lúc chạy lệnh áp dụng thay đổi tới lần đầu truy vấn Prometheus thấy alert ở trạng thái `firing`.

| Thí nghiệm | Thay đổi | Alert | Thời gian đến firing | Tín hiệu quan sát |
| --- | --- | --- | ---: | --- |
| A | Đặt `MOCK_ERROR_RATE=0.2` và tạo lại 3 container agent | `AgentHighErrorRate` | 92,8 giây | Error rate **18,93%** lúc phát hiện, vượt ngưỡng 5%. |
| D | `docker pause` 1 trong 3 replica, giữ tải và cấu hình A | `AgentInstanceDown` | 38,1 giây | Target `172.21.0.4:8000` có `up=0` và 2 target còn lại có `up=1`. |

Rule A yêu cầu lỗi kéo dài 60 giây. Rule D yêu cầu target mất liên lạc trong 30 giây. Số đo gồm thời gian triển khai hoặc pause và chu kỳ scrape/evaluation. `promtool test rules` trả `SUCCESS`. Pause để container vẫn nằm trong Docker DNS và Prometheus quan sát được `up=0`. Trong lượt chaos, Locust ghi nhận 27 phản hồi `504` trên `/ask`. Để theo dõi timeout ở tầng proxy cần đo từ Nginx vì histogram của agent chỉ ghi các request được ứng dụng xử lý. [Alert rules](06-lab-complete/benchmark-observability/production/prometheus/alert_rules.yml) · [Unit test alert](06-lab-complete/benchmark-observability/production/prometheus/alert_rules_test.yml)

Một bản agent trả lời sai vẫn có thể trả HTTP `200` và đáp ứng các ngưỡng về latency. Chạy eval định kỳ trên golden dataset và dùng quality gate của mục 3 để bắt suy giảm chất lượng theo câu hỏi.

### 4.3 Debug bằng trace

**Trace chậm** `156a81d43070c3fa1fc8640d7f5443af` trả `200`, với tổng thời gian **1772,987 ms**. Span `chat mock-llm-small` chiếm **1697,304 ms**, khoảng **95,7%** tổng thời gian. Retrieval chiếm **22,648 ms**. Span chat là bước con chiếm nhiều thời gian nhất trong trace được chọn. [Ảnh Jaeger](screenshots/jaeger-slow-trace.png)

```json
{"ts":"2026-11-25T12:01:33.649950+00:00","level":"INFO","service":"observable-agent","instance":"45a80b8d2b9c","event":"llm_call","trace_id":"156a81d43070c3fa1fc8640d7f5443af","span_id":"8d13aaf122651beb","request_id":"d9dc7e88c7b4","model":"mock-llm-small","agent_version":"v2","input_tokens":95,"output_tokens":55,"cost_usd":0.000047,"llm_ms":1697.4}
```

**Trace lỗi** `4da0c27f7d1fb6af00769e99cd11e8c1` trả `503` sau **93,887 ms**. Span `chat mock-llm-small` có event `exception` với kiểu `utils.mock_llm.LLMError` và thông báo `Upstream LLM error: 503 Service Unavailable (mock)`. Log `llm_error` dưới đây có cùng `trace_id`. [Ảnh Jaeger](screenshots/jaeger-error-trace.png)

```json
{"ts":"2026-11-25T12:04:04.782488+00:00","level":"INFO","service":"observable-agent","instance":"4f9f5bcd6fc9","event":"llm_error","trace_id":"4da0c27f7d1fb6af00769e99cd11e8c1","span_id":"64491bdb7bfb26f2","request_id":"006ffb9baa66","error":"Upstream LLM error: 503 Service Unavailable (mock)"}
```

## 5. Benchmark scaling (production, CP8)

Hai lượt dùng Locust headless với 100 users, ramp-up 10 users/giây và thời hạn 2 phút. Cùng model `mock-llm-small`, `MOCK_SLOW_RATE=0.03`, `MOCK_ERROR_RATE=0.01` và giới hạn 0,5 CPU cho mỗi replica. Tôi kiểm tra số agent qua Prometheus trước mỗi lượt và kiểm tra lại số container sau mỗi lượt. `docker compose run --no-deps` giữ nguyên số replica khi chạy Locust.

Bảng lấy từ dòng `POST /ask` trong hai CSV. Error rate tính bằng số failures chia cho request count của cùng dòng.

| Số replica | Requests | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures | Error rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [1](benchmark-results/scale_1_stats.csv) | 6.900 | 58,09 | 200 | 720 | 1.700 | 72 | 1,04% |
| [3](benchmark-results/scale_3_stats.csv) | 7.205 | 60,63 | 200 | 270 | 1.700 | 77 | 1,07% |

Scale lên 3 replica giúp throughput tăng khoảng **4,4%** và p95 giảm **62,5%**. Giữ nguyên 100 users với khoảng nghỉ giữa các request giới hạn mức tải phát sinh. p99 vẫn ở khoảng 1,7 giây, phù hợp với span mock LLM chậm quan sát trong Jaeger. Hai lượt đều có một tỷ lệ nhỏ phản hồi `503` do lỗi upstream mô phỏng.

## 6. Kết luận

### CP7

1. p99 phát hiện nhóm request chậm ở mức 3% trong khi p95 vẫn đạt ngưỡng. Theo dõi cả hai percentile giúp đọc mức ảnh hưởng rõ hơn.
2. Trong lượt thử này, concurrency 50 cho throughput cao nhất. Tăng đến 100 làm p95 vượt SLO và throughput giảm.
3. Chi phí trên mỗi câu đúng phản ánh hiệu quả của retrieval ngay cả khi số token mỗi câu tăng. Chạy eval định kỳ và theo dõi p99 sẽ giúp phát hiện riêng suy giảm chất lượng và tail latency.

### CP8

1. Với cùng mức tải, thêm replica cải thiện p95 rõ rệt trong lần đo. p99 vẫn phản ánh độ trễ mock LLM xuất hiện trong trace chậm.
2. Prometheus phát hiện lỗi qua `5xx` và phát hiện instance treo qua `up`. Jaeger và log JSON giúp đối chiếu từng lỗi theo `trace_id`.
3. Nếu đưa agent lên production, tôi sẽ theo dõi thêm tỷ lệ `5xx` và timeout tại Nginx để thấy lỗi trước khi request đến agent, đồng thời chạy eval định kỳ để đo chất lượng câu trả lời.
