# api_weight

ETL pipeline scraping body weight từ MyPTM (Cima1, Cima2) và Gallagher AMC.
Merge với Total Herd, lưu Parquet, gửi báo cáo Telegram (daily) và Outlook (weekly).

---

## Cấu trúc project

```
api_weight/
├── main.py                          # Entry point
├── run.bat                          # Shortcut Windows / Task Scheduler
├── config/
│   ├── paths.py                     # Path objects (từ path.env, tự override khi dev)
│   └── settings.py                  # Constants + RUN_MODE
├── core/
│   ├── ingest/
│   │   ├── ptm_collector.py         # MyPTM API: login + fetch (retry)
│   │   └── gallagher_collector.py   # Gallagher AMC: PKCE OAuth + incremental (retry)
│   ├── transform/
│   │   ├── structural/parser.py     # Parse raw PTM blob → DataFrame
│   │   ├── business/
│   │   │   ├── cleaner.py           # Clean EarTag
│   │   │   ├── herd_loader.py       # Load Total Herd (XLS today → parquet fallback)
│   │   │   ├── herd_merger.py       # Merge weight ↔ herd, adjust Age/DIM
│   │   │   └── classifier.py        # Phân loại Bò sữa / Bò tơ theo group_name
│   │   └── dtype.py                 # Standardize schema, cast, reorder cols
│   └── load/
│       ├── atomic.py                # tmp→rename, backup, purge backup cũ
│       ├── raw_writer.py            # Ghi raw CSV per device
│       ├── parquet_writer.py        # Append + dedup → parquet
│       └── csv_exporter.py          # Export CSV từ parquet
├── job/
│   ├── ptm_weight.py                # Job PTM
│   ├── gallagher_weight.py          # Job Gallagher
│   ├── daily_report.py              # Báo cáo ngày → Telegram
│   ├── weekly_report.py             # Báo cáo tuần → Outlook HTML
│   └── templates/weekly_report.html # Jinja2 template email
├── utils/
│   ├── logger.py                    # CSV logger mỗi lần chạy
│   ├── console.py                   # vprint() — verbose chỉ khi non-production
│   ├── health_check.py              # Pre-run checks (env, API, parquet)
│   ├── schema_loader.py             # Load herd_col_schema.xlsx (cached)
│   ├── qc_check.py                  # Validate data
│   ├── telegram_utils.py            # Gửi Telegram
│   └── outlook_utils.py             # Gửi email HTML Outlook
└── dev/
    ├── dev.env                      # Env cho chế độ dev/dry_run
    ├── debug/
    │   ├── debug_ingest.py          # Kiểm tra API connection, xem raw response
    │   ├── debug_transform.py       # Chạy pipeline, snapshot từng bước
    │   └── debug_report.py          # Render chart + HTML không gửi
    └── tests/
        ├── conftest.py              # pytest fixtures (inline, không cần file thật)
        ├── test_parser.py
        ├── test_cleaner.py
        ├── test_classifier.py
        ├── test_merger.py
        └── test_dtype.py
```

---

## Setup

```bash
pip install -r requirements.txt
pip install pytest   # cho tests
```

Tạo `D:\PYTHON_TOOLS\env\account.env` và `telegram_token.env` từ `env.example`.

---

## Chạy

```bash
# Production
python main.py
# hoặc dùng bat
run.bat

# Dev mode (dùng D:\DATABASE\DEV_ENV, verbose print bật)
$env:RUN_MODE="dev"; python main.py
run.bat dev

# Dry run (full pipeline, không ghi file, không gửi)
$env:RUN_MODE="dry_run"; python main.py
run.bat dry_run
```

---

## RUN_MODE

| Mode | Ghi file | Gửi Telegram/email | Verbose print | Paths |
|------|----------|--------------------|---------------|-------|
| `production` | ✅ | ✅ | ❌ (chỉ log CSV) | Production |
| `dev` | ✅ | ✅ | ✅ | `DEV_ENV` |
| `dry_run` | ❌ | ❌ | ✅ | Production paths (không ghi) |

---

## Debug (không cần data thật cho tests)

```bash
# Kiểm tra API connection
$env:RUN_MODE="dev"; python dev/debug/debug_ingest.py

# Xem pipeline transform step-by-step
$env:RUN_MODE="dry_run"; python dev/debug/debug_transform.py

# Render chart + HTML email, lưu vào dev/debug/_output/
$env:RUN_MODE="dry_run"; python dev/debug/debug_report.py
```

---

## Tests

```bash
# Chạy tất cả tests từ project root
pytest dev/tests/ -v

# Chạy test cụ thể
pytest dev/tests/test_parser.py -v
pytest dev/tests/test_classifier.py -v
```

Tests chạy **offline hoàn toàn** — không cần API, không cần file env thật, không cần parquet.

---

## Đường dẫn

| Loại | Key trong path.env |
|------|-------------------|
| Raw CSV per device | `DATA_LAKE_RAW` / HERD_INFO / API_WEIGHT / {DEVICE} |
| CSV cleaned | `DATA_LAKE_CSV` / HERD_INFO / API_WEIGHT |
| Parquet master | `DATA_MARK` / HERD_INFO / API_WEIGHT / weight_db_api.parquet |
| Total Herd parquet | `DATA_MARK` / INFO_HERD / total_herd.parquet |
| Schema reference | `D:\PYTHON_TOOLS\env\herd_col_schema.xlsx` |
| Log | `D:\Log\api_weight_run_log.csv` |

Credentials và email → `account.env` | Telegram → `telegram_token.env` (không commit).

---

## Schema parquet (`weight_db_api.parquet`)

| Cột | Dtype | Ghi chú |
|-----|-------|---------|
| `source` | str | PTM / GALLAGHER |
| `device` | str | CIMA1 / CIMA2 / GALLAGHER_1 |
| `date` | str | YYYY-MM-DD |
| `time` | str | HH:MM |
| `no` | str | Cow ID từ herd |
| `ear_tag` | str | RFID cleaned |
| `group_name` | str | Từ herd |
| `group_feed` | str | Từ herd |
| `animal_type` | str | cow / heifer / other |
| `weight_kg` | float32 | |
| `age_month` | float32 | Từ age_month_fix hoặc computed |
| `age_days` | Int16 | Adjusted về ngày cân |
| `dim` | Int16 | Adjusted về ngày cân |
| `lac_no` | Int8 | |
| `loaded_at` | str | Timestamp load |

**Dedup key:** `[date, ear_tag, device]` — sort `loaded_at` asc → keep last

---

## Git

```bash
# Update thường ngày
cd D:\PYTHON_TOOLS\project\info_herd\api_weight
git add .
git commit -m "fix: mô tả thay đổi"
git push
```

Không commit: `*.env`, `*.parquet`, `*.csv`, `gallagher_tokens.json`, `dev/debug/_output/`
