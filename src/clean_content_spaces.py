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
    """判斷字元是否為 CJK 中文字（含擴展/相容字區）、中文全形標點符號"""
    if not c:
        return False
    cp = ord(c)
    # CJK Unified Ideographs & Extension A
    if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
        return True
    # CJK Symbols and Punctuation (excluding U+3000 ideographic space)
    if 0x3000 <= cp <= 0x303F:
        return cp != 0x3000
    # Fullwidth Forms (excluding fullwidth English letters and numbers)
    if 0xFF00 <= cp <= 0xFFEF:
        if (0xFF10 <= cp <= 0xFF19) or (0xFF21 <= cp <= 0xFF3A) or (0xFF41 <= cp <= 0xFF5A):
            return False
        return True
    # CJK Compatibility Ideographs
    if 0xF900 <= cp <= 0xFAFF:
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
    # 1. 識別並提取最後署名（使用 rightmost title 搜尋，支援單字姓名）
    titles = ["主任委員", "副主任委員", "院長", "部長", "署長", "召集人", "副召集人"]
    rightmost_title = None
    rightmost_idx = -1
    for t in titles:
        idx = text.rstrip().rfind(t)
        if idx > rightmost_idx:
            rightmost_idx = idx
            rightmost_title = t
            
    sig_text = ""
    if rightmost_idx != -1:
        name_part = text.rstrip()[rightmost_idx + len(rightmost_title):]
        stripped_name = name_part.strip().replace(" ", "").replace("　", "")
        # 判定剩餘長度是否合理，且僅包含中文/圈號/0/O/相容字區
        if 1 <= len(stripped_name) <= 10 and re.match(r'^[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff〇○O0]+$', stripped_name):
            # 清理名字並標準化字元
            cleaned_name = stripped_name.replace("○", "〇")
            cleaned_name = re.sub(r'[0O]', '〇', cleaned_name)
            
            sig_text = f"{rightmost_title} {cleaned_name}"
            text = text[:rightmost_idx].rstrip()

    # 2. 移除中文字元（含擴展、相容漢字）與標點間的空格
    cjk_char = r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\u3007〇○]'
    cjk_punc = r'[，。、；：？！（）「」『』—～【】〈〉｛｝．]'
    cjk_or_punc = f'(?:{cjk_char}|{cjk_punc})'
    
    while True:
        new_text = re.sub(f'({cjk_or_punc})\\s+({cjk_or_punc})', r'\1\2', text)
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
