import json
import os
import re
import sqlite3
import sys
import zhconv

# 避免 Windows 終端機 CP950 編碼問題
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
JSON_PATH = os.path.join(BASE_DIR, "gplAll_1150630.json")
DB_PATH = os.path.join(BASE_DIR, "gpl.db")

def is_cjk_or_punctuation(c):
    """判斷字元是否為 CJK 中文字、中文標點或中文數字 〇/○"""
    if not c:
        return False
    # 中文字範圍
    if '\u4e00' <= c <= '\u9fa5' or c == '〇' or c == '○':
        return True
    # 常見中文標點與數字關聯字
    if c in ['，', '。', '、', '；', '：', '？', '！', '（', '）', '「', '」', '『', '』', '—', '～', '第', '號', '年', '月', '日', '元']:
        return True
    return False

def replace_zeros_contextual(text):
    """
    上下文判定替換：將 0、O、○ 標準化為 〇
    - ○ 一律轉換為 〇
    - 0 與 O：若鄰接英文或非零數字，保留不變；若鄰接中文字元、標點，則轉換。
    """
    # 1. 先將白色圈號 ○ 一律轉換為 〇
    text = text.replace("○", "〇")
    
    def repl(match):
        val = match.group(0)
        start = match.start()
        end = match.end()
        
        prev_char = text[start - 1] if start > 0 else ""
        next_char = text[end] if end < len(text) else ""
        
        # 若為標準西式數字的一部分 (鄰接 1-9)，保留
        if (prev_char.isdigit() and prev_char != '0') or (next_char.isdigit() and next_char != '0'):
            return val
            
        # 若為英文字彙的一部分，保留
        is_prev_alpha = prev_char.isalpha() and not ('\u4e00' <= prev_char <= '\u9fa5')
        is_next_alpha = next_char.isalpha() and not ('\u4e00' <= next_char <= '\u9fa5')
        if is_prev_alpha or is_next_alpha:
            return val
            
        # 若鄰接中文字元、標點，或者是獨立占位符，則進行替換
        if is_cjk_or_punctuation(prev_char) or is_cjk_or_punctuation(next_char):
            return "〇" * len(val)
            
        return val

    # 匹配連續的 0 或 O
    return re.sub(r'[0O]+', repl, text)

def clean_spaces(text):
    """
    字間空格清理與最後署名格式化
    - 移除所有中文字與標點符號間的空格
    - 縮減中英數邊界的連續空格為單一空格
    - 最後署名（如 主任委員 陳金德）在職稱與姓名間僅保留一空格，且姓名無空格。
    """
    # 1. 識別並提取公文最末端的署名
    sig_pattern = re.compile(
        r'(主任委員|副主任委員|院長|部長|署長|召集人|副召集人)\s*([\u4e00-\u9fa5\s〇○O0]{2,12})$'
    )
    
    match_sig = sig_pattern.search(text)
    sig_text = ""
    if match_sig:
        title = match_sig.group(1)
        name_part = match_sig.group(2)
        
        # 清理姓名部分：移除所有空格，並將 0/O/○ 轉為 〇
        cleaned_name = name_part.replace(" ", "").replace("　", "")
        cleaned_name = cleaned_name.replace("○", "〇")
        cleaned_name = re.sub(r'[0O]', '〇', cleaned_name)
        
        sig_text = f"{title} {cleaned_name}"
        # 暫時將署名從內文中切離，避免干擾主要內文的空格清理
        text = text[:match_sig.start()].rstrip()

    # 2. 移除中文字與標點之間的空格
    cjk_char = r'[\u4e00-\u9fa5\u3007〇○]'
    cjk_punc = r'[，。、；：？！（）「」『』—～]'
    cjk_or_punc = f'(?:{cjk_char}|{cjk_punc})'
    
    # 循環替代，確保處理陳 金 德等多個字間空格
    while True:
        new_text = re.sub(f'({cjk_or_punc})\s+({cjk_or_punc})', r'\1\2', text)
        if new_text == text:
            break
        text = new_text

    # 3. 縮減中英數邊界的連續空格為單一空格
    text = re.sub(r'\s+', ' ', text)

    # 4. 重新接回格式化後的署名
    if sig_text:
        text = f"{text} {sig_text}"
        
    return text.strip()

def clean_data():
    if not os.path.exists(JSON_PATH):
        print(f"錯誤: 找不到 JSON 檔案 {JSON_PATH}")
        return
        
    print(f"載入 JSON 檔案: {JSON_PATH}...")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated_count = 0
    samples = []
    
    print("開始執行內容欄位空格清理與字元標準化...")
    
    for item in data:
        item_id = int(item.get("項次"))
        content = item.get("內容", "")
        if not content:
            continue
            
        # 1. 執行清洗
        cleaned_content = replace_zeros_contextual(content)
        cleaned_content = clean_spaces(cleaned_content)
        
        # 2. 判斷是否有變更
        if cleaned_content != content:
            item["內容"] = cleaned_content
            
            # 同步更新 SQLite 資料庫 (包含 content 與 clean_content)
            clean_cnt_db = re.sub(r'\s+', ' ', cleaned_content).strip()
            cursor.execute(
                "UPDATE letters SET content = ?, clean_content = ? WHERE id = ?",
                (cleaned_content, clean_cnt_db, item_id)
            )
            
            updated_count += 1
            # 收集特定項次作為樣本展示
            if item_id in [1, 134, 146, 243, 294]:
                samples.append({
                    "項次": item_id,
                    "原內容尾部": content[-150:].replace("\n", " "),
                    "新內容尾部": cleaned_content[-150:].replace("\n", " ")
                })
                
    conn.commit()
    conn.close()
    
    # 3. 安全寫入 JSON
    tmp_path = JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(JSON_PATH):
        os.remove(JSON_PATH)
    os.rename(tmp_path, JSON_PATH)
    
    print("\n" + "="*40)
    print(f"清洗完成！共更新 {updated_count} 筆資料。")
    print("="*40)
    
    print("\n--- 樣本比對驗證 ---")
    for s in samples:
        print(f"項次: {s['項次']}")
        print(f"  原內容尾部: {s['原內容尾部']}")
        print(f"  新內容尾部: {s['新內容尾部']}")
        print("-" * 50)

if __name__ == "__main__":
    clean_data()
