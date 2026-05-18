# api_weight

ETL pipeline scraping body weight data từ MyPTM (Cima1, Cima2) và Gallagher AMC (Gallagher_1).
Merge với Total Herd data, lưu Parquet, gửi báo cáo Telegram (daily) và Outlook (weekly).

---

## Cấu trúc project

```
api_weight/
├── main.py                          # Entry point
├── config/
│   ├── paths.py                     # Tất cả Path objects (load từ path.env)
│   └── settings.py                  # Constants nghiệp vụ (không có credentials)
├── core/
│   ├── ingest/
│   │   ├── ptm_collector.py         # MyPTM API: login + fetch Cima1/Cima2
│   │   └── gallagher_collector.py   # Gallagher AMC API: PKCE OAuth + incremental fetch
│   ├── transform/
│   │   ├── structural/
│   │   │   └── parser.py            # Parse raw PTM blob → DataFrame
│   │   ├── business/
│   │   │   ├── cleaner.py           # Clean EarTag
│   │   │   ├── herd_loader.py       # Load Total Herd (XLS today → parquet fallback)
│   │   │   ├── herd_merger.py       # Merge weight ↔ herd, adjust Age/DIM
│   │   │   └── classifier.py        # Phân loại Bò sữa / Bò tơ theo group_name
│   │   └── dtype.py                 # Standardize schema, cast types, reorder cols
│   └── load/
│       ├── atomic.py                # tmp→rename, backup, purge backup cũ
│       ├── raw_writer.py            # Ghi raw CSV per device
│       ├── parquet_writer.py        # Append + dedup → weight_db_api.parquet
│       └── csv_exporter.py          # Export CSV từ parquet
├── job/
│   ├── ptm_weight.py                # Job PTM (Cima1 + Cima2)
│   ├── gallagher_weight.py          # Job Gallagher
│   ├── daily_report.py              # Báo cáo ngày → Telegram
│   ├── weekly_report.py             # Báo cáo tuần → Outlook HTML
│   └── templates/
│       └── weekly_report.html       # Jinja2 template email
└── utils/
    ├── logger.py                    # CSV logger mỗi lần chạy
    ├── qc_check.py                  # Validate data
    ├── telegram_utils.py            # Gửi ảnh/text Telegram
    └── outlook_utils.py             # Gửi email HTML Outlook
```

---

## Setup

### 1. Cài thư viện

```bash
pip install -r requirements.txt
```

### 2. Tạo file env

Copy `env.example` → `D:\PYTHON_TOOLS\env\account.env` và điền thông tin thực:

```
PTM_USERNAME=...
PTM_PASSWORD=...
GALLAGHER_FARM_ID=...
GALLAGHER_USERNAME=...
GALLAGHER_PASSWORD=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID_3=...
MAIL_SEND=......
MAIL_TO=...
MAIL_CC=...
ALERT_MAIL_TO=...........
```

`path.env` đặt tại `LOCAL\path.env` (xem mẫu trong env.example).

### 3. Chạy

```bash
python main.py
```

---

## Đường dẫn dữ liệu

| Loại | Đường dẫn |
|------|-----------|
| Raw CSV per device | `` |
| CSV cleaned (source 1) | `` |
| CSV legacy (source 2) | `` |
| **Parquet master** | `` |
| Total Herd parquet | `` |
| Temp chart | `` (xóa sau gửi) |
| Log | `` |

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
| `group_name` | str | Từ herd merge |
| `group_feed` | str | Từ herd merge |
| `cattle_type` | str | milking_cow / heifer / other |
| `weight_kg` | float32 | |
| `age_month` | float32 | Từ age_month_fix (herd DB) hoặc computed |
| `age_days` | Int16 | Đã adjust về ngày cân |
| `dim` | Int16 | Đã adjust về ngày cân |
| `lac_no` | Int8 | |
| `loaded_at` | str | Timestamp lúc load |

**Dedup key:** `[date, ear_tag, device]` — keep last (bản có `loaded_at` lớn nhất)

---

## Phân loại Bò sữa / Bò tơ

Dựa trên `group_name` sau khi merge herd (không phụ thuộc vào device):

| Loại | Điều kiện |
|------|-----------|
| `milking_cow` | group_name startswith `M`, `C`, hoặc `HOS` |
| `heifer` | group_name match `H[1-8]` |
| `other` | còn lại |

---

## Weekly Report — Coverage threshold

| Tuần trong tháng | Ngưỡng tối thiểu |
|-----------------|-----------------|
| Tuần 1 (ngày 1–7) | 10% |
| Tuần 2 (ngày 8–14) | 20% |
| Tuần 3+ (ngày 15+) | 30% |

---

## Git & Security

- **KHÔNG commit**: `*.env`, `gallagher_tokens.json`, `*.parquet`, `*.csv`, `*.png`
- Xem `.gitignore` để biết đầy đủ danh sách
- Mọi credentials đặt trong `account.env` (không commit)
- Paths đặt trong `path.env` (không commit)
