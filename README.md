# 政府採購法解釋函令前置處理專案 (Government Procurement Interpretive Letters Pre-processing)

本專案旨在對政府採購法的解釋函令數據（`gplAll_1150630.json`）進行清洗、解析與結構化處理，並將結果儲存至 SQLite 資料庫，以便後續進行高效的檢索、統計或 AI 語意分析。

## 功能特色
1. **資料清洗**：移除文字內容中多餘的換行與空白字元。
2. **法條解析**：使用正規表達式將「依據採購法條文」拆解為獨立的關聯資料（法規名稱、條、項、款），以便進行精確的法條關聯查詢。
3. **關鍵字提取**：整合 `jieba` 中文斷詞，利用 TF-IDF 演算法自動為每筆解釋函令提取關鍵字。
4. **資料庫儲存**：建立 SQLite 資料庫 (`gpl.db`)，定義雙表結構（主表 `letters` 與關聯表 `letter_laws`）並建立索引以提升效能。

## 專案結構
```text
├── gplAll_1150630.json   # 原始解釋函令資料 (JSON 格式)
├── gpl.db                # 處理後產生的 SQLite 資料庫 (執行後產生)
├── requirements.txt      # Python 套件依賴項目
├── README.md             # 專案說明文件
└── src/
    ├── db.py             # 資料庫 Schema 定義與初始化
    └── preprocess.py     # 資料前置處理、解析與匯入腳本
```

## 安裝與執行步驟

### 1. 安裝依賴套件
本專案建議使用 Python 3.8+。請在專案目錄下執行以下指令安裝所需套件：
```bash
pip install -r requirements.txt
```

### 2. 執行前置處理與匯入
執行 `src/preprocess.py` 開始進行資料處理與匯入：
```bash
python src/preprocess.py
```
執行成功後，專案根目錄下會產生 `gpl.db` 資料庫檔案。

## 資料庫 Schema 說明

### `letters` (解釋函令主表)
- `id` (INTEGER, 主鍵): 對應原始資料的「項次」。
- `doc_id` (TEXT): 發文字號（例如：`工程企字第11501002971號`）。
- `subject` (TEXT): 主題。
- `raw_laws` (TEXT): 原始依據採購法條文。
- `upload_date` (TEXT): 上網日期。
- `publish_date` (TEXT): 發文日期。
- `url` (TEXT): PCC 官網詳細內容連結。
- `content` (TEXT): 原始內容。
- `clean_content` (TEXT): 清洗後去除了多餘空白的文字內容。
- `keywords` (TEXT): 由 jieba 提取的關鍵字，以逗號分隔。

### `letter_laws` (關聯法條解析表)
- `id` (INTEGER, 主鍵): 自動遞增。
- `letter_id` (INTEGER): 對應 `letters.id` 的外鍵。
- `law_name` (TEXT): 解析後的法規名稱（例如：`政府採購法`、`機關委託技術服務廠商評選及計費辦法`）。
- `article` (TEXT): 條（例如：`第22條`）。
- `paragraph` (TEXT): 項（例如：`第1項`）。
- `subparagraph` (TEXT): 款（例如：`第7款`）。
- `raw_spec` (TEXT): 原始解析的單一法條字串。
