import json
import os
import argparse
import shutil
import re
import sys
import sqlite3
import zhconv

# 設定標準輸出/錯誤以 UTF-8 解碼，避免 Windows 終端機 CP950 罕用字編碼錯誤
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# 用於清除與格式化備註字頭的正規表達式
PREFIX_CLEANER = re.compile(
    r"^(?:備註|附註|補充備註|註記|附記|補充說明|【註】|\[註\]|（註）|\(註\)|【註[0-9一二三四五]】|\[註[0-9]\]|註[0-9一二三四五]?|註」)[:：\s.．。]+"
)

# 用於在內文中尋找備註標頭的正規表達式 (新增選用括號匹配如 【備註】)
NOTE_HEADER_PATTERN = re.compile(
    r"[【\[（\(「]?(?:備註|附註|補充備註|註記|附記|補充說明|註[0-9一二三四五]?|註」)[】\]）\)」]?(?:[:：\s.．。]*|$)"
)



# 用於在署名後方識別備註的簽章正規表達式
SIG_PATTERN = re.compile(r"(?:主任委員|院長|部長|署長)\s*[\u4e00-\u9fa5\s]{2,8}")

STOP_INDICATORS = ["停止適用", "不再援用"]

# 支援字間空格的公文大口標頭 Regex (針對"說明"加入負向後瞻)
HEADER_PATTERNS = {
    "主旨": re.compile(r"主\s*旨\s*[:：]"),
    "說明": re.compile(r"(?<!補充)(?<!附註)(?<!特別)(?<!詳細)說\s*明\s*[:：]"),
    "辦法": re.compile(r"辦\s*法\s*[:：]"),
    "正本": re.compile(r"正\s*本\s*[:：]"),
    "副本": re.compile(r"副\s*本\s*[:：]")
}


def clean_note_text(text):
    """清理備註文字：去字頭、簡繁轉換、去編號與首尾空白"""
    text = text.strip()
    # 繁簡字體標準化
    text = zhconv.convert(text, 'zh-hant')
    
    # 清理備註字頭
    cleaned = PREFIX_CLEANER.sub("", text).strip()
    cleaned = re.sub(r"^[【\[（\(]註[0-9一二三四五]+[\]】）\)]", "", cleaned).strip()
    cleaned = re.sub(r"^[【\[（\(]註[\]】）\)]", "", cleaned).strip()
    cleaned = re.sub(r"^註[0-9一二三四五]+", "", cleaned).strip()
    cleaned = re.sub(r"^[0-9]+[.\s．、]+", "", cleaned).strip()
    cleaned = re.sub(r"^[:：\s.．。]+", "", cleaned).strip()
    return cleaned

def split_sub_points(text):
    """將包含多個子項目的備註拆分為獨立清單"""
    text = text.strip()
    split_pattern = re.compile(r"\s*(?:[0-9]+[.\s．、]+|註[0-9一二三四五]+[:：\s.．。]*)")
    
    matches = list(split_pattern.finditer(text))
    if not matches:
        return [text]
        
    points = []
    last_idx = 0
    for i, m in enumerate(matches):
        start = m.start()
        if i == 0 and start == 0:
            continue
        points.append(text[last_idx:start].strip())
        last_idx = start
        
    points.append(text[last_idx:].strip())
    
    cleaned_points = []
    for pt in points:
        pt_strip = pt.strip()
        if pt_strip:
            cleaned_points.append(pt_strip)
            
    return cleaned_points if cleaned_points else [text]

def is_valid_note_header(match, text):
    """
    安全性檢查：驗證匹配到的「備註/補充說明」是否為內文句子中的普通關鍵字。
    - 括號類顯式標頭 (如 【註】、[註]、「註」) 直接判定為有效。
    - 包含冒號者亦直接視為有效 (如 註: 備註：)
    - 否則 (如：補充說明、備註)，若後續接有「乙案」、「說明」等，判定為無效。
    """
    start = match.start()
    matched_text = match.group(0)
    
    # 1. 括號類開頭直接判定有效
    if any(b in matched_text for b in ['【', '[', '「', '（', '(']):
        return True
        
    # 2. 如果包含冒號，也視為顯式標頭，直接判定有效
    if '：' in matched_text or ':' in matched_text:
        return True
        
    # 3. 普通文字類進行安全排除
    after_text = text[start + len(matched_text):start + len(matched_text) + 15]
    if any(k in after_text for k in ["乙案", "辦理", "規定", "部分條文", "事項", "如下", "內容", "作法", "程序"]):
        return False
        
    return True




def extract_notes_from_content(content):
    """分析並抽取公文「內容」中首尾的備註部分"""
    content_strip = content.strip()
    moved_notes = []
    cleaned_content = content_strip
    
    # --- 1. 抽取主旨前備註 (Prefix Notes) ---
    match_主旨 = HEADER_PATTERNS["主旨"].search(content_strip)
    if match_主旨:
        主旨_idx = match_主旨.start()
        prefix_part = content_strip[:主旨_idx].strip()
        if prefix_part:
            match_note = NOTE_HEADER_PATTERN.search(prefix_part)
            # 必須為有效備註且長度在合理範圍內
            if (match_note and is_valid_note_header(match_note, prefix_part)) or any(si in prefix_part for si in STOP_INDICATORS):
                if len(prefix_part) < 300:
                    # 檢查是否為空備註
                    note_content = prefix_part
                    if match_note:
                        note_content = prefix_part[match_note.end():]
                    note_content_clean = re.sub(r'^[:：\s.．。]+', '', note_content).strip()
                    if len(note_content_clean) > 2:
                        moved_notes.append(prefix_part)
                        cleaned_content = content_strip[主旨_idx:].strip()
                        content_strip = cleaned_content  # 更新後續比對內容
                    
    # --- 2. 抽取署名或正/副本後備註 (Suffix Notes) ---
    last_section_idx = -1
    for name, pattern in HEADER_PATTERNS.items():
        matches = list(pattern.finditer(content_strip))
        if matches:
            idx = matches[-1].start()
            if idx > last_section_idx:
                last_section_idx = idx
                
    if last_section_idx == -1:
        last_section_idx = 0
        
    suffix_part = content_strip[last_section_idx:]
    
    # 尋找顯式備註標頭
    matches = list(NOTE_HEADER_PATTERN.finditer(suffix_part))
    valid_match = None
    for m in matches:
        if is_valid_note_header(m, suffix_part):
            valid_match = m
            break
            
    if valid_match:
        m_start = valid_match.start()
        note_block = suffix_part[m_start:].strip()
        
        # 驗證備註是否包含實質內容（非空備註）
        matched_header = valid_match.group(0)
        note_content = note_block[len(matched_header):].strip()
        note_content_clean = re.sub(r'^[:：\s.．。]+', '', note_content).strip()
        
        if len(note_content_clean) > 2:
            moved_notes.append(note_block)
            cleaned_content = content_strip[:last_section_idx + m_start].strip()
    else:
        # 無顯式標頭，檢查署名後之語意備註 (Fallback)
        sig_matches = list(SIG_PATTERN.finditer(suffix_part))
        if sig_matches:
            last_sig = sig_matches[-1]
            s_end = last_sig.end()
            
            text_after = suffix_part[s_end:].strip()
            if text_after and any(si in text_after for si in STOP_INDICATORS):
                if len(text_after) < 400: # 確保非大段誤判內文
                    moved_notes.append(text_after)
                    cleaned_content = content_strip[:last_section_idx + s_end].strip()
                    
    return cleaned_content, moved_notes

def merge_notes(moved_points, existing_note):
    """將抽取出的備註與目的地欄位既有備註合併、去重與簡繁轉化"""
    cleaned_moved = [clean_note_text(p) for p in moved_points]
    
    # 解析現有備註
    existing_points = []
    if existing_note:
        parts = re.split(r"(?:<p>|<br>|\n)+", existing_note)
        for part in parts:
            part = part.strip()
            if part:
                existing_points.extend(split_sub_points(part))
                
    cleaned_existing = [clean_note_text(p) for p in existing_points]
    
    final_cleaned_points = []
    
    def add_with_dedup(list_of_memos, new_memo):
        if not new_memo:
            return
        for idx, existing in enumerate(list_of_memos):
            if new_memo == existing:
                return
            elif new_memo in existing:
                # 已包含於現有較完整備註中
                return
            elif existing in new_memo:
                # 較長備註覆蓋舊備註
                list_of_memos[idx] = new_memo
                return
        list_of_memos.append(new_memo)
        
    # 先放入新擷取的，再放入原有的，做子字串比對去重
    for cp in cleaned_moved:
        add_with_dedup(final_cleaned_points, cp)
    for ep in cleaned_existing:
        add_with_dedup(final_cleaned_points, ep)
        
    # 格式化編號
    if not final_cleaned_points:
        return ""
    return "\n".join(f"{idx+1}. {pt}" for idx, pt in enumerate(final_cleaned_points))

def process_record(record):
    """處理單筆紀錄"""
    content = record.get("內容", "")
    existing_note = record.get("廢止或補充之備註", "").strip()
    
    cleaned_content, extracted_raw_notes = extract_notes_from_content(content)
    
    # 若無提取，仍需對既有備註做標準化格式整理
    if not extracted_raw_notes:
        if existing_note:
            cleaned_existing = []
            parts = re.split(r"(?:<p>|<br>|\n)+", existing_note)
            for p in parts:
                if p.strip():
                    cleaned_existing.extend(split_sub_points(p))
            
            final_points = []
            for ep in cleaned_existing:
                ct = clean_note_text(ep)
                if ct:
                    # 子字串去重
                    is_dup = False
                    for idx, fp in enumerate(final_points):
                        if ct == fp:
                            is_dup = True
                            break
                        elif ct in fp:
                            is_dup = True
                            break
                        elif fp in ct:
                            final_points[idx] = ct
                            is_dup = True
                            break
                    if not is_dup:
                        final_points.append(ct)
            
            formatted_note = ""
            if final_points:
                formatted_note = "\n".join(f"{idx+1}. {pt}" for idx, pt in enumerate(final_points))
                
            if formatted_note != existing_note:
                return True, content, formatted_note, "Formatted existing notes in '廢止或補充之備註'."
        return False, content, existing_note, "No notes to migrate."
        
    # 執行提取點拆分與合併
    moved_points = []
    for raw_note in extracted_raw_notes:
        moved_points.extend(split_sub_points(raw_note))
        
    final_note_str = merge_notes(moved_points, existing_note)
    
    if cleaned_content != content or final_note_str != existing_note:
        desc = f"Migrated {len(moved_points)} note points from '內容' to '廢止或補充之備註'."
        return True, cleaned_content, final_note_str, desc
        
    return False, content, existing_note, "No notes to migrate."

def run_check(json_path):
    """掃描 JSON 檔案並輸出可能需要移轉備註的紀錄摘要"""
    if not os.path.exists(json_path):
        print(f"Error: File not found at {json_path}")
        return 1
        
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return 1
            
    candidates = []
    for record in data:
        item_id = record.get("項次", "")
        content = record.get("內容", "")
        
        cleaned_content, extracted = extract_notes_from_content(content)
        if extracted:
            candidates.append({
                "項次": item_id,
                "發文字號": record.get("發文字號", ""),
                "提取備註": extracted
            })
            
    print(f"=== Scan Results for {os.path.basename(json_path)} ===")
    print(f"Total records scanned: {len(data)}")
    print(f"Records requiring note migration: {len(candidates)}")
    if candidates:
        print("\nTarget Records Detail:")
        for c in candidates[:50]:  # 列出前 50 筆作預覽
            print(f"  - 項次 {c['項次']} ({c['發文字號']}): {len(c['提取備註'])} note block(s) detected.")
            for i, note in enumerate(c['提取備註']):
                snippet = note.strip().replace("\n", " ")
                if len(snippet) > 80:
                    snippet = snippet[:80] + "..."
                print(f"    [{i+1}] {snippet}")
        if len(candidates) > 50:
            print(f"\n... and {len(candidates) - 50} more records.")
    return 0

def run_migrate(json_path, backup=True, output_report=None):
    """執行實際資料移轉與資料庫同步"""
    if not os.path.exists(json_path):
        print(f"Error: File not found at {json_path}")
        return 1
        
    # 1. 備份
    if backup:
        backup_path = json_path + ".backup"
        try:
            shutil.copyfile(json_path, backup_path)
            print(f"Created backup file at {backup_path}")
        except Exception as e:
            print(f"Failed to create backup: {e}")
            return 1
            
    # 2. 載入 JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return 1
            
    modified_records = []
    skipped_records = []
    
    # 3. 處理每筆資料
    for record in data:
        item_id = record.get("項次", "")
        content = record.get("內容", "")
        existing = record.get("廢止或補充之備註", "")
        
        try:
            modified, new_content, new_note, desc = process_record(record)
            if modified:
                record["內容"] = new_content
                record["廢止或補充之備註"] = new_note
                modified_records.append({
                    "項次": item_id,
                    "發文字號": record.get("發文字號", ""),
                    "原內容尾端": content[-120:].strip(),
                    "新內容尾端": new_content[-120:].strip(),
                    "原備註": existing,
                    "新備註": new_note,
                    "描述": desc
                })
        except Exception as e:
            skipped_records.append({
                "項次": item_id,
                "發文字號": record.get("發文字號", ""),
                "Error": str(e)
            })
            
    # 4. 寫回 JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Database successfully updated. Modified {len(modified_records)} records.")
    
    # 5. 同步更新 SQLite 資料庫
    db_path = os.path.join(os.path.dirname(json_path), "gpl.db")
    if os.path.exists(db_path):
        print("正在將更新同步至 SQLite 資料庫...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        db_updated = 0
        try:
            for r in modified_records:
                letter_id = int(r["項次"])
                # 重新查詢該筆 JSON 物件以確保寫入的值是正確的
                record = next(item for item in data if int(item.get("項次")) == letter_id)
                new_content = record["內容"]
                new_memo = record["廢止或補充之備註"]
                
                # 計算清洗後的內容（移除空白等），以配合舊 db.py 中的寫法
                clean_cnt = re.sub(r'\s+', ' ', new_content).strip()
                
                cursor.execute(
                    "UPDATE letters SET content = ?, clean_content = ?, memo = ? WHERE id = ?",
                    (new_content, clean_cnt, new_memo, letter_id)
                )
                db_updated += 1
            conn.commit()
            print(f"SQLite 資料庫更新完成，共同步 {db_updated} 筆資料。")
        except Exception as e:
            conn.rollback()
            print(f"資料庫更新失敗: {e}")
        finally:
            conn.close()
            
    # 6. 產出報告
    if output_report:
        report_lines = []
        report_lines.append(f"# Notes Migration & Cleanup Report")
        report_lines.append(f"Target Database: `{os.path.basename(json_path)}`  ")
        report_lines.append(f"Total Records: {len(data)}  ")
        report_lines.append(f"Modified Records: {len(modified_records)}  ")
        report_lines.append(f"Skipped Records (Errors): {len(skipped_records)}  \n")
        
        if skipped_records:
            report_lines.append("## ⚠️ Skipped Records (Requires Manual Review)")
            for r in skipped_records:
                report_lines.append(f"* **項次 {r['項次']}** ({r['發文字號']}): Error - `{r['Error']}`")
            report_lines.append("\n")
            
        if modified_records:
            report_lines.append("## 📝 Modified Records Detail")
            for r in modified_records:
                report_lines.append(f"### 🔹 [項次 {r['項次']}] ({r['發文字號']})")
                report_lines.append(f"**Action**: {r['描述']}  ")
                report_lines.append(f"**Content Ending (Before)**: `... {r['原內容尾端'].replace('\n', ' ')}`  ")
                report_lines.append(f"**Content Ending (After)**: `... {r['新內容尾端'].replace('\n', ' ')}`  ")
                report_lines.append(f"**Remarks (Before)**: `{repr(r['原備註'])}`  ")
                report_lines.append(f"**Remarks (After)**:  ")
                for pt in r['新備註'].split('\n'):
                    report_lines.append(f"  {pt}  ")
                report_lines.append("\n" + "-" * 40 + "\n")
                
        with open(output_report, 'w', encoding='utf-8') as rf:
            rf.write("\n".join(report_lines))
        print(f"Verification report saved to: {output_report}")
        
    return 0

def main():
    parser = argparse.ArgumentParser(description="JSON Public Letters Notes Migrator Utility")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    
    # Check subcommand
    check_parser = subparsers.add_parser("check", help="Scan JSON file and list records requiring note migration.")
    check_parser.add_argument("json_path", help="Absolute path to the JSON database file.")
    
    # Migrate subcommand
    migrate_parser = subparsers.add_parser("migrate", help="Migrate notes from '內容' to '廢止或補充之備註' in the JSON file.")
    migrate_parser.add_argument("json_path", help="Absolute path to the JSON database file.")
    migrate_parser.add_argument("--no-backup", action="store_false", dest="backup", help="Disable automatic backup file creation.")
    migrate_parser.add_argument("--output-report", help="Path to save the detailed before/after markdown report.")
    
    args = parser.parse_args()
    
    if args.command == "check":
        return run_check(args.json_path)
    elif args.command == "migrate":
        return run_migrate(args.json_path, backup=args.backup, output_report=args.output_report)
    else:
        parser.print_help()
        return 0

if __name__ == "__main__":
    sys.exit(main())
