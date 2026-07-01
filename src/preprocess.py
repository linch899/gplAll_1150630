import json
import os
import re
import time
import random
import argparse
import sqlite3
import sys
import requests
from bs4 import BeautifulSoup
import urllib3
from db import init_db, get_db_connection

# 避免 Windows 終端機因 CP950 不支援某些罕用字而導致 print 崩潰
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

# 停用 SSL 警告

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 嘗試匯入 jieba 用於中文斷詞
try:
    import jieba
    import jieba.analyse
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

# 檔案路徑設定
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
JSON_PATH = os.path.join(BASE_DIR, "gplAll_1150630.json")

def clean_text(text):
    """清洗文字內容，移除多餘的空白與換行"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_law_relation(raw_law_str):
    """解析依據採購法條文字串"""
    if not raw_law_str:
        return []
    
    tokens = re.split(r'[、；,;]', raw_law_str)
    relations = []
    
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        
        pattern = r'^(.+?)(第\d+(?:條之\d+|條))?(第\d+項)?(第\d+款)?$'
        match = re.match(pattern, token)
        
        if match:
            law_name = match.group(1).strip()
            article = match.group(2)
            paragraph = match.group(3)
            subparagraph = match.group(4)
            
            relations.append({
                "law_name": law_name,
                "article": article,
                "paragraph": paragraph,
                "subparagraph": subparagraph,
                "raw_spec": token
            })
        else:
            relations.append({
                "law_name": token,
                "article": None,
                "paragraph": None,
                "subparagraph": None,
                "raw_spec": token
            })
            
    return relations

def extract_keywords(text, top_k=5):
    """使用 jieba 提取關鍵字"""
    if not HAS_JIEBA or not text:
        return ""
    try:
        keywords = jieba.analyse.extract_tags(text, topK=top_k)
        return ",".join(keywords)
    except Exception:
        return ""

def infer_authority_from_doc_id(doc_id):
    """
    當網頁標頭遺失或僅有文別（例如「函」）時，
    根據「發文字號」的前綴字元推導發文機關。
    """
    if not doc_id:
        return "行政院公共工程委員會"
        
    # 移除年份前綴如 (88)、(89)
    clean_id = re.sub(r'^\(\d+\)', '', doc_id).strip()
    
    if any(k in clean_id for k in ["工程", "工企", "工管", "工技", "工資", "工訴", "工稽", "工促", "院授工"]):
        return "行政院公共工程委員會"
    elif any(k in clean_id for k in ["內營", "內授營", "營署", "中營"]):
        return "內政部營建署"
    elif any(k in clean_id for k in ["內地", "內民"]):
        return "內政部"
    elif any(k in clean_id for k in ["勞職", "勞動", "職業"]):
        return "勞動部"
    elif any(k in clean_id for k in ["法律", "法政", "法廉", "法"]):
        return "法務部"
    elif any(k in clean_id for k in ["經商", "經授工", "經標"]):
        return "經濟部"
    elif "環署" in clean_id:
        return "行政院環境保護署"
    elif "原民" in clean_id:
        return "原住民族委員會"
    elif any(k in clean_id for k in ["主會", "總處", "院授主"]):
        return "行政院主計總處"
    elif any(k in clean_id for k in ["財稅", "財保"]):
        return "財政部"
    elif "文授資" in clean_id:
        return "文化部"
    elif "健保" in clean_id:
        return "衛生福利部中央健康保險署"
    elif "台票" in clean_id:
        return "中央銀行"
        
    return "行政院公共工程委員會"

def fetch_authority_and_suffix(url, doc_id, retries=1):
    """
    從指定的工程會網址爬取發文機關與文別後綴。
    若失敗會重試一次。
    """
    if not url:
        return None, None
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for attempt in range(retries + 1):
        try:
            # 每次請求之間加入 1.0 ~ 2.5 秒的隨機延遲
            delay = random.uniform(1.0, 2.5)
            time.sleep(delay)
            
            response = requests.get(url, headers=headers, verify=False, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                title_el = soup.find(class_='title_1s')
                if title_el:
                    title_text = title_el.get_text(strip=True)
                    if title_text:
                        # 解析標頭，例如 "行政院公共工程委員會 函" -> ("行政院公共工程委員會", "函")
                        parts = title_text.rsplit(maxsplit=1)
                        if len(parts) == 2:
                            authority = parts[0].strip()
                            suffix = parts[1].strip()
                        else:
                            authority = title_text.strip()
                            suffix = "函"
                            
                        # 防禦性處理：若抓取的機關字數過短（如僅有「函」或「令」），使用發文字號進行推導
                        if len(authority) <= 2 or authority in ["函", "令", "公告", "抄本"]:
                            authority = infer_authority_from_doc_id(doc_id)
                            suffix = title_text.strip() if title_text.strip() in ["函", "令", "公告"] else "函"
                            
                        return authority, suffix
                return None, None
            else:
                print(f"  [警告] 請求失敗 (HTTP {response.status_code})，網址: {url}")
        except (requests.RequestException, Exception) as e:
            print(f"  [警告] 請求異常 (嘗試 {attempt + 1}/{retries + 1}): {e}")
            
        if attempt < retries:
            print("  [重試] 等待 5 秒後進行重試...")
            time.sleep(5)
            
    return None, None

def save_json_incrementally(data_list):
    """安全地將資料寫入暫存檔後覆蓋原 JSON 檔"""
    tmp_path = JSON_PATH + ".tmp"
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data_list, f, ensure_ascii=False, indent=2)
        if os.path.exists(JSON_PATH):
            os.remove(JSON_PATH)
        os.rename(tmp_path, JSON_PATH)
    except Exception as e:
        print(f"儲存 JSON 暫存檔時發生錯誤: {e}")

def process_data(limit=None, reset_db=False):
    """主處理流程"""
    # 1. 初始化資料庫
    init_db(drop_existing=reset_db)
    
    # 2. 讀取 JSON 檔案
    if not os.path.exists(JSON_PATH):
        print(f"錯誤: 找不到 JSON 資料檔案 {JSON_PATH}")
        return
        
    print(f"正在讀取 {JSON_PATH}...")
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    total_records = len(raw_data)
    print(f"讀取完成，共 {total_records} 筆原始資料。")
    
    # 統計指標
    crawled_count = 0
    skipped_count = 0
    failed_count = 0
    processed_records = []
    
    # 3. 逐筆處理與爬取
    print("開始進行資料清洗與網頁爬取...")
    
    limit_num = limit if limit is not None else total_records
    
    for idx, item in enumerate(raw_data):
        if idx >= limit_num:
            # 超過限制筆數，但仍需保留未處理的原始資料以供後續使用
            processed_records.append(item)
            continue
            
        print(f"正在處理第 {idx + 1}/{limit_num} 筆 (項次: {item.get('項次')})...")
        
        # 取得欄位值
        doc_id = item.get("發文字號", "").strip()
        url = item.get("連結網址", "").strip()
        authority = item.get("發文機關", "")
        
        # 檢查是否已處理過 (斷點續傳：必須有發文機關且長度大於 2，以排除先前失敗寫入的「函」)
        has_processed = "發文機關" in item and authority and len(authority) > 2
        
        suffix = "函"
        
        if has_processed:
            skipped_count += 1
            print(f"  [跳過] 已有發文機關資料: '{authority}'")
        else:
            # 執行網頁爬取
            fetched_auth, fetched_suffix = fetch_authority_and_suffix(url, doc_id, retries=1)
            if fetched_auth:
                authority = fetched_auth
                suffix = fetched_suffix
                crawled_count += 1
                print(f"  [成功] 爬取發文機關: '{authority}', 文別後綴: '{suffix}'")
                
                # 修正發文字號後綴
                if suffix and not doc_id.endswith(suffix):
                    doc_id = f"{doc_id}{suffix}"
            else:
                failed_count += 1
                print(f"  [失敗] 無法取得網頁標頭，保留原欄位值。")
        
        # 重整欄位順序 (項次 -> 分類索引 -> 發文機關 -> 發文字號 -> 主題...)
        ordered_item = {
            "項次": item.get("項次"),
            "分類索引": item.get("分類索引", {"章": "", "節": "", "項": ""}),
            "發文機關": authority,
            "發文字號": doc_id,
            "主題": item.get("主題", "").strip(),
            "依據採購法條文": item.get("依據採購法條文", "").strip(),
            "上網日期": item.get("上網日期", "").strip(),
            "發文日期": item.get("發文日期", "").strip(),
            "連結網址": url,
            "內容": item.get("內容", ""),
            "廢止或補充之備註": item.get("廢止或補充之備註", "").strip()
        }
        
        processed_records.append(ordered_item)
        
        # 每 50 筆做一次增量存檔 (僅在有實際爬取時存檔以節省 I/O)
        if (idx + 1) % 50 == 0 and crawled_count > 0:
            print(f"  [存檔] 已處理至 {idx + 1} 筆，進行增量存檔...")
            save_json_incrementally(processed_records + raw_data[idx + 1:])
            
    # 最終寫入 JSON
    save_json_incrementally(processed_records)
    print("\n[JSON 更新完成]")
    
    # 4. 同步寫入 SQLite 資料庫
    print("正在將更新後的資料同步至 SQLite 資料庫...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    db_inserted = 0
    laws_inserted = 0
    
    try:
        # 只將已處理的 processed_records 寫入資料庫
        for item in processed_records:
            try:
                letter_id = int(item.get("項次"))
            except (ValueError, TypeError):
                continue
                
            # 分類索引次欄位
            cat = item.get("分類索引", {"章": "", "節": "", "項": ""})
            cat_chap = cat.get("章", "")
            cat_sec = cat.get("節", "")
            cat_item = cat.get("項", "")
            
            auth = item.get("發文機關", "")
            doc_id = item.get("發文字號", "")
            raw_laws = item.get("依據採購法條文", "")
            content = item.get("內容", "")
            
            clean_cnt = clean_text(content)
            keywords = extract_keywords(clean_cnt, top_k=8)
            
            # 寫入主表
            cursor.execute("""
                INSERT OR REPLACE INTO letters (
                    id, category_chapter, category_section, category_item, dispatch_authority,
                    doc_id, subject, raw_laws, upload_date, publish_date, url, content, memo, clean_content, keywords
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                letter_id, cat_chap, cat_sec, cat_item, auth,
                doc_id, item.get("主題"), raw_laws, item.get("上網日期"), item.get("發文日期"),
                item.get("連結網址"), content, item.get("廢止或補充之備註"), clean_cnt, keywords
            ))
            db_inserted += 1
            
            # 解析並寫入關聯法條表
            parsed_laws = parse_law_relation(raw_laws)
            for law in parsed_laws:
                cursor.execute("""
                    INSERT INTO letter_laws (
                        letter_id, law_name, article, paragraph, subparagraph, raw_spec
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    letter_id, law["law_name"], law["article"], law["paragraph"], law["subparagraph"], law["raw_spec"]
                ))
                laws_inserted += 1
                
        conn.commit()
        print(f"資料庫同步完成！共匯入主表 {db_inserted} 筆，解析法條關聯 {laws_inserted} 筆。")
    except Exception as e:
        conn.rollback()
        print(f"資料庫寫入失敗: {e}")
        raise e
    finally:
        conn.close()
        
    # 5. 輸出統計結果
    print("\n" + "="*40)
    print("           數據處理與爬蟲統計結果")
    print("="*40)
    print(f" 總資料筆數   : {total_records} 筆")
    print(f" 本次設定限制 : {limit_num} 筆")
    print(f" 成功爬取筆數 : {crawled_count} 筆")
    print(f" 跳過(已處理) : {skipped_count} 筆")
    print(f" 爬取失敗筆數 : {failed_count} 筆")
    
    # 統計發文機關分布
    auth_stats = {}
    for item in processed_records[:limit_num]:
        auth = item.get("發文機關", "")
        if auth:
            auth_stats[auth] = auth_stats.get(auth, 0) + 1
            
    if auth_stats:
        print("-" * 40)
        print(" 發文機關分布統計:")
        for auth, count in sorted(auth_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {auth}: {count} 筆")
    print("="*40)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="政府採購解釋函令資料前置處理與爬蟲")
    parser.add_argument("--limit", type=int, default=None, help="限制處理的筆数")
    parser.add_argument("--reset-db", action="store_true", help="是否重設資料庫")
    args = parser.parse_args()
    
    process_data(limit=args.limit, reset_db=args.reset_db)
