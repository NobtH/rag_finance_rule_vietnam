rag_pgsql_project/
├── app/                    # (1) Code chính
│   ├── __init__.py
│   ├── config.py           # Cấu hình (DB, model name, ...)
│   ├── database/           # (2) Kết nối và thao tác PostgreSQL
│   │   ├── __init__.py
│   │   ├── connection.py   # Kết nối DB
│   │   ├── schema.sql      # File SQL tạo bảng
│   │   └── vector_store.py # Các hàm insert/truy vấn embedding
│   ├── embedding/          # (3) Vector hóa văn bản
│   │   ├── __init__.py
│   │   └── encoder.py      # Dùng sentence-transformers
│   ├── retriever/          # (4) Tìm kiếm context phù hợp
│   │   ├── __init__.py
│   │   └── search.py
│   ├── generator/          # (5) Sinh câu trả lời từ context
│   │   ├── __init__.py
│   │   └── generate.py     # Dùng T5, GPT, OpenAI...
│   ├── rag_pipeline.py     # (6) Pipeline RAG end-to-end
│   └── main.py             # Entry point (CLI hoặc FastAPI)
│
├── data/                   # Chứa văn bản gốc
│   └── corpus.txt
│
├── requirements.txt        # Thư viện cần cài
├── .env                    # Biến môi trường (DB URL, API KEY,...)
└── README.md               # Giới thiệu project
# rag_finance_rule_vietnam
# rag_finance_rule_vietnam
