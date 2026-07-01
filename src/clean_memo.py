import json
import os
import re
import sqlite3
import sys
import zhconv

# 避免 Windows 終端機因 CP950 不支援某些罕用字而導致 print 崩潰
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(errors='replace')


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
JSON_PATH = os.path.join(BASE_DIR, "gplAll_1150630.json")
DB_PATH = os.path.join(BASE_DIR, "gpl.db")

def clean_memo_text(text):
    """清理備註文字，移除 HTML 換行標籤與常見的『註：』、『備註：』字頭"""
    if not text:
        return ""
    # 移除 HTML 換行
    text = re.sub(r'<br\s*/?>|<p\s*/?>', ' ', text)
    # 移除多個連續空白
    text = re.sub(r'\s+', ' ', text)
    # 移除各類備註字頭
    text = re.sub(r'^(?:【註】|註[：:]|備註[：:]|函備註[：:]|令備註[：:]|※|備註|註)\s*', '', text)
    return text.strip()

def merge_notes(note_extracted, note_existing):
    """
    合併兩份備註並進行繁簡轉換與去重。
    如果有一段內容是另一段的子字串，自動保留較長（較完整）者。
    """
    clean_a = clean_memo_text(note_extracted)
    clean_b = clean_memo_text(note_existing)
    
    # 繁體標準化
    norm_a = zhconv.convert(clean_a, 'zh-hant').strip()
    norm_b = zhconv.convert(clean_b, 'zh-hant').strip()
    
    memos_list = []
    
    def add_with_dedup(list_of_memos, new_memo):
        if not new_memo:
            return
        for idx, existing in enumerate(list_of_memos):
            if new_memo == existing:
                return
            elif new_memo in existing:
                # 新備註已包含在現有備註中，跳過
                return
            elif existing in new_memo:
                # 新備註比現有備註更長且包含現有，替換為較長的備註
                list_of_memos[idx] = new_memo
                return
        list_of_memos.append(new_memo)
        
    # 先加原備註，再加提取的備註
    add_with_dedup(memos_list, norm_b)
    add_with_dedup(memos_list, norm_a)
    
    return memos_list

def format_memos(memos_list):
    """將備註列表格式化為 1. XXX\n2. YYY"""
    if not memos_list:
        return ""
    formatted = []
    for idx, memo in enumerate(memos_list):
        formatted.append(f"{idx + 1}. {memo}")
    return "\n".join(formatted)

def clean_project_data():
    if not os.path.exists(JSON_PATH):
        print(f"錯誤: 找不到 JSON 檔案 {JSON_PATH}")
        return
        
    print(f"載入 JSON 檔案: {JSON_PATH}...")
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    standard_suffixes = {"函", "令", "會議紀錄", "解釋書函", "講習會", "書函"}
    updated_count = 0
    samples = []
    
    print("開始掃描並清洗發文字號與備註...")
    
    for item in data:
        doc_id = item.get("發文字號", "").strip()
        if not doc_id:
            continue
            
        if "號" in doc_id:
            parts = doc_id.split("號")
            suffix_part = parts[-1].strip()
            
            # 判斷是否為需要處理的夾帶備註資料
            if suffix_part and suffix_part not in standard_suffixes:
                # 1. 識別正確的公文後綴
                if "會議紀錄" in suffix_part or "會議記錄" in suffix_part:
                    clean_suffix = "會議紀錄"
                elif "解釋書函" in suffix_part:
                    clean_suffix = "解釋書函"
                elif "書函" in suffix_part:
                    clean_suffix = "書函"
                elif "令" in suffix_part:
                    clean_suffix = "令"
                elif "函" in suffix_part:
                    clean_suffix = "函"
                elif "講習會" in suffix_part:
                    clean_suffix = "講習會"
                else:
                    clean_suffix = "函"
                    
                # 2. 還原發文字號
                restored_doc_id = parts[0] + "號" + clean_suffix
                
                # 3. 提取備註內容 (僅在後綴以公文種類開頭時，才移除該字元，避免誤傷「通函」等詞)
                if suffix_part.startswith(clean_suffix):
                    extracted_note = suffix_part[len(clean_suffix):].strip()
                else:
                    extracted_note = suffix_part
                
                # 4. 與原備註合併並去重

                existing_memo = item.get("廢止或補充之備註", "").strip()
                merged_list = merge_notes(extracted_note, existing_memo)
                formatted_memo = format_memos(merged_list)
                
                # 5. 更新 JSON 物件
                item["發文字號"] = restored_doc_id
                item["廢止或補充之備註"] = formatted_memo
                
                # 6. 更新 SQLite 資料庫
                letter_id = int(item.get("項次"))
                cursor.execute(
                    "UPDATE letters SET doc_id = ?, memo = ? WHERE id = ?",
                    (restored_doc_id, formatted_memo, letter_id)
                )
                
                updated_count += 1
                if len(samples) < 3:
                    samples.append({
                        "項次": letter_id,
                        "原發文字號": doc_id,
                        "新發文字號": restored_doc_id,
                        "新備註": formatted_memo
                    })
                    
    conn.commit()
    conn.close()
    
    # 7. 安全寫入更新後的 JSON 檔案
    tmp_path = JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if os.path.exists(JSON_PATH):
        os.remove(JSON_PATH)
    os.rename(tmp_path, JSON_PATH)
    
    print("\n" + "="*40)
    print(f"清洗完成！共更新 {updated_count} 筆資料。")
    print("="*40)
    
    print("\n--- 樣本驗證 ---")
    for s in samples:
        print(f"項次: {s['項次']}")
        print(f"  原發文字號: {s['原發文字號']}")
        print(f"  新發文字號: {s['新發文字號']}")
        print(f"  新備註內容:\n{s['新備註']}")
        print("-" * 40)

if __name__ == "__main__":
    clean_project_data()
