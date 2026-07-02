import json
import re
import os
import sys

# Force UTF-8 stdout
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

JSON_PATH = "d:/AI Workplace/antigravity/1150630_政府採購解釋函令前置作業/gplAll_1150630.json"
DB_PATH = "d:/AI Workplace/antigravity/1150630_政府採購解釋函令前置作業/gpl.db"
REPORT_PATH = "C:/Users/linch/.gemini/antigravity/brain/da3f36bb-0e9e-4783-9218-8fe1edb34845/scratch/newlines_injection_report.txt"

HEADER_PATTERNS = {
    "主旨": re.compile(r"主\s*旨\s*[:：]"),
    "說明": re.compile(r"(?<!補充)(?<!附註)(?<!特別)(?<!詳細)說\s*明\s*[:：]"),
    "辦法": re.compile(r"辦\s*法\s*[:：]"),
    "正本": re.compile(r"正\s*本\s*[:：]"),
    "副本": re.compile(r"副\s*本\s*[:：]")
}

SIG_PATTERN = re.compile(r"(?:主任委員|院長|部長|署長)\s*[\u4e00-\u9fa5\s]{2,8}$")

LIST_MARKER_PAT = re.compile(
    r"(?:"
    r"[一二三四五六七八九十百]+、|"                 # Level 1
    r"[(（][一二三四五六七八九十]+[)）]|"            # Level 2
    r"[１２３４５６７８９０]+[、]|\d+\.|"           # Level 3
    r"[(（][１２３４５６７８９０\d]+[)）]"          # Level 4
    r")"
)

def is_valid_list_item_start(match, text):
    start = match.start()
    end = match.end()
    matched_str = match.group(0)
    
    # 1. Exclude ROC Years (e.g. (八八), (九十))
    if matched_str.startswith(('(', '（')) and matched_str.endswith((')', '）')):
        inner = matched_str[1:-1].strip()
        roc_years = {
            "八八", "八九", "九十", "九一", "九二", "九三", "九四", "九五", "九六", "九七", "九八", "九九",
            "一〇〇", "一〇O", "一百", "一〇一", "一〇二", "一〇三", "一〇四", "一〇五", "一〇六", "一〇七", "一〇八", "一〇九",
            "一一〇", "一一一", "一一二", "一一三", "一一四", "一一五"
        }
        if inner in roc_years:
            return False
            
    # 2. Exclude References (e.g. 第(二)款)
    if start > 0:
        prev_text = text[:start].rstrip()
        if prev_text and prev_text[-1] == '第':
            return False
            
    if end < len(text):
        next_char = text[end]
        if next_char in ['款', '目', '條', '項', '段']:
            return False
            
    # 3. Check preceding character separator
    if start == 0:
        return True
        
    prev_non_space = text[:start].rstrip()
    if not prev_non_space:
        return True
        
    last_char = prev_non_space[-1]
    valid_separators = ['。', '；', ';', '：', ':', '」', '』', '）', ')', '\n']
    if last_char in valid_separators:
        return True
        
    return False

def inject_newlines(content):
    """
    Parses flat text, inserts \n between main sections,
    and splits list items inside '說明' or '辦法' with \n.
    """
    content = content.strip()
    
    # 1. Find all main headers and signature
    matches = []
    for key in ["主旨", "說明", "辦法", "正本", "副本"]:
        for m in HEADER_PATTERNS[key].finditer(content):
            matches.append((m.start(), m.end(), key, m.group(0)))
            
    # Find signature block
    sig_match = SIG_PATTERN.search(content)
    if sig_match:
        matches.append((sig_match.start(), sig_match.end(), "署名", sig_match.group(0)))
        
    matches.sort(key=lambda x: x[0])
    
    if not matches:
        return content
        
    # Reconstruct segments
    segments = []
    
    # If there is text before first match
    if matches[0][0] > 0:
        segments.append(('前置', "", content[:matches[0][0]].strip()))
        
    for i in range(len(matches)):
        start, end, key, matched_str = matches[i]
        next_start = matches[i+1][0] if i + 1 < len(matches) else len(content)
        block_content = content[end:next_start].strip()
        segments.append((key, matched_str, block_content))
        
    # Process each segment
    final_parts = []
    for key, header, body in segments:
        if key in ['前置']:
            final_parts.append(body)
            continue
            
        if key == '署名':
            final_parts.append(f"{header}{body}")
            continue
            
        if key in ['主旨', '正本', '副本']:
            final_parts.append(f"{header}{body}")
            continue
            
        # For '說明' and '辦法', split sub-levels inside
        if key in ['說明', '辦法']:
            # Find all valid list item starts
            body_matches = list(LIST_MARKER_PAT.finditer(body))
            valid_body_matches = [m for m in body_matches if is_valid_list_item_start(m, body)]
            
            if not valid_body_matches:
                final_parts.append(f"{header}{body}")
                continue
                
            # Reconstruct body with newlines
            body_parts = []
            last_idx = 0
            
            # If there is text before the first list item (e.g. intro text right after 說明：)
            if valid_body_matches[0].start() > 0:
                intro = body[:valid_body_matches[0].start()].strip()
                if intro:
                    body_parts.append(intro)
                    
            for j in range(len(valid_body_matches)):
                m_start = valid_body_matches[j].start()
                m_end = valid_body_matches[j].end()
                m_next = valid_body_matches[j+1].start() if j + 1 < len(valid_body_matches) else len(body)
                
                chunk = body[m_start:m_next].strip()
                body_parts.append(chunk)
                
            # Combine header and body
            # If the body starts directly with a list item, put it on a new line
            # Otherwise, keep intro text on the same line as the header, and subsequent items on new lines
            if valid_body_matches[0].start() == 0:
                final_parts.append(f"{header}\n" + "\n".join(body_parts))
            else:
                # First part is intro text
                final_parts.append(f"{header}{body_parts[0]}\n" + "\n".join(body_parts[1:]))
                
    # Join all segments with single newline
    return "\n".join(final_parts)

def run_simulation():
    if not os.path.exists(JSON_PATH):
        print("JSON not found.")
        return
        
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Loaded {len(data)} items for simulation.")
    
    modified_count = 0
    report_lines = []
    
    for item in data:
        item_id = item.get("項次")
        content = item.get("內容", "")
        if not content:
            continue
            
        injected = inject_newlines(content)
        if injected != content:
            modified_count += 1
            if modified_count <= 100:  # Write first 100 changes to report
                report_lines.append(f"項次 {item_id} ({item.get('發文字號')}):")
                report_lines.append(f"  [BEFORE]: {repr(content[-250:])}")
                report_lines.append(f"  [AFTER]:")
                for line in injected.split("\n"):
                    report_lines.append(f"    | {line}")
                report_lines.append("-" * 60 + "\n")
                
    print(f"Simulation completed. {modified_count} records will be updated.")
    
    with open(REPORT_PATH, "w", encoding="utf-8") as f_out:
        f_out.write(f"=== Newline Injection Simulation Report ===\n")
        f_out.write(f"Total Modified Records: {modified_count}\n\n")
        f_out.write("\n".join(report_lines))
        
    print(f"Report saved to: {REPORT_PATH}")

def run_actual_update():
    if not os.path.exists(JSON_PATH):
        print("JSON not found.")
        return
        
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"Updating JSON file: {JSON_PATH}...")
    
    # SQLite Connection
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated = 0
    for item in data:
        item_id = int(item.get("項次"))
        content = item.get("內容", "")
        if not content:
            continue
            
        injected = inject_newlines(content)
        if injected != content:
            item["內容"] = injected
            
            # Sync to SQLite database
            clean_cnt = re.sub(r'\s+', ' ', injected).strip()
            cursor.execute(
                "UPDATE letters SET content = ?, clean_content = ? WHERE id = ?",
                (injected, clean_cnt, item_id)
            )
            updated += 1
            
    conn.commit()
    conn.close()
    
    # Save JSON safely
    tmp_path = JSON_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    if os.path.exists(JSON_PATH):
        os.remove(JSON_PATH)
    os.rename(tmp_path, JSON_PATH)
    
    print(f"Successfully updated {updated} records in JSON and SQLite DB.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run_actual_update()
    else:
        run_simulation()
