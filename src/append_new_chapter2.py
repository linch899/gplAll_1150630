import docx
import json
import os
import re

def main():
    docx_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第二章\第二章(112.1開始增加).docx"
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\gplAll_1150630.json"
    output_json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第二章\第二章.json"

    # 1. Load existing 第二章.json
    if not os.path.exists(output_json_path):
        print(f"Error: Existing file {output_json_path} not found.")
        return
        
    with open(output_json_path, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
    print(f"Loaded {len(existing_data)} existing entries from 第二章.json.")

    # 2. Load gplAll_1150630.json
    with open(json_path, "r", encoding="utf-8") as f:
        gpl_data = json.load(f)

    # Build map of 發文字號 -> entry in gplAll
    gpl_map = {}
    for entry in gpl_data:
        doc_id = entry.get("發文字號", "").strip()
        if doc_id:
            std_id = re.sub(r'\s+', '', doc_id)
            gpl_map.setdefault(std_id, []).append(entry)

    # Section mappings
    section_mapping = {
        "2.1": "投標須知",
        "2.2": "工程採購契約",
        "2.3": "財物採購契約",
        "2.4": "勞務採購契約",
        "2.5": "聲明書",
        "2.6": "切結書",
        "2.7": "其他招標相關文件或表格"
    }

    # 3. Read docx and parse into blocks
    doc = docx.Document(docx_path)
    blocks = []
    current_sec_num = None
    current_paras = []
    
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if re.match(r'^2\.\d+$', text):
            if current_sec_num and current_paras:
                blocks.append((current_sec_num, current_paras))
            current_sec_num = text
            current_paras = []
        else:
            if current_sec_num is not None:
                current_paras.append(text)
                
    if current_sec_num and current_paras:
        blocks.append((current_sec_num, current_paras))

    print(f"Extracted {len(blocks)} blocks from new docx.")

    new_entries = []
    current_chapter = "第二章 招標相關文件範本及表格"

    # 4. Extract and match
    for idx, (sec_num, paras) in enumerate(blocks):
        sec_name = section_mapping.get(sec_num, sec_num)
        
        # Get absolute last line of text in block
        all_lines = []
        for p_text in paras:
            all_lines.extend([line.strip() for line in p_text.split('\n') if line.strip()])
        last_line = all_lines[-1] if all_lines else ""
        
        # Find dispatch number
        match = re.search(r'(\(\d+\)[^\s，、。]+字第\d+號(?:函|令)?)', last_line)
        if not match:
            match = re.search(r'([^\s，、。]+字第\d+號(?:函|令)?)', last_line)
            
        doc_id = match.group(1) if match else last_line
        doc_id = re.sub(r'.*?日', '', doc_id).strip()
        std_doc_id = re.sub(r'\s+', '', doc_id)
        
        # Search match
        matches = gpl_map.get(std_doc_id, [])
        if not matches:
            for k, v in gpl_map.items():
                if std_doc_id in k or k in std_doc_id:
                    matches = v
                    break
                    
        if matches:
            db_entry = matches[0]
            new_entry = json.loads(json.dumps(db_entry)) # copy
            new_entry["分類索引"] = {
                "章": current_chapter,
                "節": sec_name,
                "項": ""
            }
            new_entries.append(new_entry)
        else:
            print(f"Warning: No match found for block {idx} '{doc_id}' in {sec_name}.")
            # Fallback placeholder if unmatched (we expect 0 unmatched)
            new_entry = {
                "項次": f"2-new-{idx:02d}",
                "分類索引": {
                    "章": current_chapter,
                    "節": sec_name,
                    "項": ""
                },
                "發文機關": "行政院公共工程委員會",
                "發文字號": doc_id,
                "主題": paras[0] if paras else "",
                "依據採購法條文": "",
                "上網日期": "",
                "發文日期": "",
                "連結網址": "",
                "內容": "\n".join(paras),
                "廢止或補充之備註": ""
            }
            new_entries.append(new_entry)

    # 5. Append and Save
    combined_data = existing_data + new_entries
    
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(combined_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully appended {len(new_entries)} new entries.")
    print(f"Total entries in 第二章.json now: {len(combined_data)}")

if __name__ == "__main__":
    main()
