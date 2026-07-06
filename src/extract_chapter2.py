import docx
import json
import os
import re
from docx.oxml.ns import qn

def extract_date(last_line):
    # Try to extract date like "88年7月14日" or "109年1月31日"
    match = re.search(r'(\d+)年\s*(\d+)月\s*(\d+)日', last_line)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        # Format: e.g., "880714" or "1090131"
        return f"{year}{month:02d}{day:02d}"
    return ""

def main():
    docx_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第二章\第二章_組長版.docx"
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\gplAll_1150630.json"
    output_json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第二章\第二章.json"

    doc = docx.Document(docx_path)

    # Load JSON
    with open(json_path, "r", encoding="utf-8") as f:
        gpl_data = json.load(f)

    # Build map of 發文字號 -> entry in gpl_data
    gpl_map = {}
    for entry in gpl_data:
        doc_id = entry.get("發文字號", "").strip()
        if doc_id:
            std_id = re.sub(r'\s+', '', doc_id)
            gpl_map.setdefault(std_id, []).append(entry)

    current_chapter = "第二章 招標相關文件範本及表格"
    current_section = ""

    extracted_entries = []
    unmatched_count = 0

    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue
        
        # Check if it's a section header or a list paragraph
        pPr = p._p.get_or_add_pPr()
        numPr = pPr.find(qn('w:numPr'))
        
        is_bullet = False
        is_section_header = False
        
        if numPr is not None:
            ilvl = numPr.find(qn('w:ilvl'))
            numId = numPr.find(qn('w:numId'))
            ilvl_val = int(ilvl.get(qn('w:val'))) if ilvl is not None else 0
            numId_val = int(numId.get(qn('w:val'))) if numId is not None else 0
            
            if numId_val in [1, 3] and ilvl_val == 0:
                is_section_header = True
            elif numId_val in [2, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15] and ilvl_val == 0:
                is_bullet = True

        if is_section_header:
            current_section = text
            continue
            
        if is_bullet or (numPr is not None and numPr.find(qn('w:ilvl')) is None):
            # Process bullet item
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if not lines:
                continue
            
            last_line = lines[-1]
            
            # Clean last line to extract the dispatch number
            match = re.search(r'(\(\d+\)[^\s，、。]+字第\d+號(?:函|令)?)', last_line)
            if not match:
                match = re.search(r'([^\s，、。]+字第\d+號(?:函|令)?)', last_line)
            
            doc_id = match.group(1) if match else last_line
            doc_id = re.sub(r'.*?日', '', doc_id) # remove everything before and including '日'
            doc_id = doc_id.strip()
            
            std_doc_id = re.sub(r'\s+', '', doc_id)
            
            # Try to find match in gpl_map
            matches = []
            if std_doc_id in gpl_map:
                matches = gpl_map[std_doc_id]
            else:
                for k, v in gpl_map.items():
                    if std_doc_id in k or k in std_doc_id:
                        matches = v
                        break

            if len(matches) > 0:
                # We take the first matched database entry, copy it, and update index
                db_entry = matches[0]
                new_entry = json.loads(json.dumps(db_entry)) # deep copy
                new_entry["分類索引"] = {
                    "章": current_chapter,
                    "節": current_section,
                    "項": ""
                }
                extracted_entries.append(new_entry)
            else:
                # Handle unmatched: Option A (placeholder)
                unmatched_count += 1
                placeholder_id = f"2-{unmatched_count:02d}"
                
                # Extract subject/title from first line of text
                subject = lines[0] if lines else ""
                
                # Clean up subject if it starts with "主旨：" or similar
                subject = re.sub(r'^主旨：', '', subject)
                
                # Build content
                content = "\n".join(lines)
                
                # Extract date from last line
                doc_date = extract_date(last_line)
                
                # Determine dispatch authority
                authority = "行政院公共工程委員會"
                if "內政部" in last_line:
                    authority = "內政部"
                
                new_entry = {
                    "項次": placeholder_id,
                    "分類索引": {
                        "章": current_chapter,
                        "節": current_section,
                        "項": ""
                    },
                    "發文機關": authority,
                    "發文字號": doc_id + ("函" if not doc_id.endswith(("函", "令")) else ""),
                    "主題": subject,
                    "依據採購法條文": "",
                    "上網日期": "",
                    "發文日期": doc_date,
                    "連結網址": "",
                    "內容": content,
                    "廢止或補充之備註": ""
                }
                extracted_entries.append(new_entry)

    # Save to JSON
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(extracted_entries, f, ensure_ascii=False, indent=2)
        
    print(f"Extraction completed successfully.")
    print(f"Total entries written: {len(extracted_entries)}")
    print(f"Unmatched entries handled: {unmatched_count}")

if __name__ == "__main__":
    main()
