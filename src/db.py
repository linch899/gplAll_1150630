import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "gpl.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(drop_existing=False):
    """初始化資料庫表結構"""
    conn = get_db_connection()
    cursor = conn.cursor()

    if drop_existing:
        print("正在清除舊的資料表...")
        cursor.execute("DROP TABLE IF EXISTS letter_laws")
        cursor.execute("DROP TABLE IF EXISTS letters")

    # 1. 解釋函令主表 (新增分類索引與發文機關欄位)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS letters (
            id INTEGER PRIMARY KEY,          -- 對應 JSON 中的 "項次"
            category_chapter TEXT,           -- 分類索引 - 章
            category_section TEXT,           -- 分類索引 - 節
            category_item TEXT,              -- 分類索引 - 項
            dispatch_authority TEXT,         -- 發文機關 (例如: 行政院公共工程委員會)
            doc_id TEXT,                     -- 發文字號 (例如: 工程企字第11501002971號函)
            subject TEXT,                    -- 主題
            raw_laws TEXT,                   -- 原始依據採購法條文
            upload_date TEXT,                -- 上網日期 (格式: YYYYMMDD)
            publish_date TEXT,               -- 發文日期 (格式: YYYYMMDD)
            url TEXT,                        -- 連結網址
            content TEXT,                    -- 內容
            memo TEXT,                       -- 廢止或補充之備註
            clean_content TEXT,              -- 清洗後的內容 (去除多餘空白等)
            keywords TEXT                    -- 斷詞提取的關鍵字 (逗號分隔)
        )
    """)

    # 2. 關聯法條解析表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS letter_laws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            letter_id INTEGER,               -- 對應 letters.id
            law_name TEXT,                   -- 法規名稱 (例如: 政府採購法, 共同供應契約實施辦法)
            article TEXT,                    -- 條 (例如: 第22條)
            paragraph TEXT,                  -- 項 (例如: 第1項)
            subparagraph TEXT,               -- 款 (例如: 第7款)
            raw_spec TEXT,                   -- 原始解析字串
            FOREIGN KEY (letter_id) REFERENCES letters (id) ON DELETE CASCADE
        )
    """)

    # 建立索引以提升查詢效能
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letters_doc_id ON letters(doc_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letters_publish_date ON letters(publish_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letter_laws_letter_id ON letter_laws(letter_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_letter_laws_lookup ON letter_laws(law_name, article)")

    conn.commit()
    conn.close()
    print(f"資料庫初始化成功，檔案路徑: {DB_PATH}")

if __name__ == "__main__":
    init_db(drop_existing=True)
