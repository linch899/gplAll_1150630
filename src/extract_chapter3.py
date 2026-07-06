import docx
import json
import re
import os

def get_date_val(item):
    date_str = item.get("發文日期", "").strip()
    if not date_str:
        return 0
    if len(date_str) < 4:
        return 0
    try:
        # e.g., "880714" or "1090131"
        year_str = date_str[:-4]
        month_str = date_str[-4:-2]
        day_str = date_str[-2:]
        return int(year_str) * 10000 + int(month_str) * 100 + int(day_str)
    except ValueError:
        return 0

def extract_date(last_line):
    match = re.search(r'(\d+)年\s*(\d+)月\s*(\d+)日', last_line)
    if match:
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        return f"{year}{month:02d}{day:02d}"
    return ""

def clean_doc_id(doc_id):
    # Remove leading spaces, trailing marks, date prefix
    doc_id = re.sub(r'.*?日', '', doc_id)
    doc_id = doc_id.strip()
    return doc_id

def parse_leader_version(docx_path, gpl_map):
    doc = docx.Document(docx_path)
    
    chinese_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", 
                    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十"]
    
    sections = [
        "確認採購類型", "確認採購金額", "擬定招標方式", "擬定決標原則", "廠商資格訂定",
        "技術規格訂定與同等品", "成立採購評選委員會", "擬訂投標須知",
        "擬訂評選項目、評審標準及評定方式", "擬訂採購價金及標單",
        "擬訂服務費用及價金之給付條件", "擬訂規範、圖說及履約期限",
        "擬訂契約草案", "招標文件公開閱覽", "其他招標文件事項"
    ]
    
    section_map = {}
    for idx, sec in enumerate(sections):
        section_map[sec] = f"第{chinese_nums[idx]}節 {sec}"
        
    current_section = ""
    current_item = ""
    
    section_index = 0
    item_index_in_section = 0
    
    extracted = []
    unmatched_count = 0
    
    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue
            
        pPr = p._p.get_or_add_pPr()
        numPr = pPr.find(docx.oxml.ns.qn('w:numPr'))
        
        ilvl_val = -1
        numId_val = -1
        if numPr is not None:
            ilvl = numPr.find(docx.oxml.ns.qn('w:ilvl'))
            numId = numPr.find(docx.oxml.ns.qn('w:numId'))
            ilvl_val = int(ilvl.get(docx.oxml.ns.qn('w:val'))) if ilvl is not None else -1
            numId_val = int(numId.get(docx.oxml.ns.qn('w:val'))) if numId is not None else -1
            
        is_chapter = (numId_val == 40 and ilvl_val == 0)
        is_section = (ilvl_val == 1)
        is_item = (ilvl_val == 2)
        is_bullet = (numPr is not None and ilvl_val == 0) or (p.style.name == "List Paragraph" and not is_chapter and not is_section and not is_item)
        
        if is_chapter:
            continue
            
        if is_section:
            section_index += 1
            sec_name = text
            # Map to canonical section name with prefix
            current_section = section_map.get(sec_name, f"第{chinese_nums[section_index-1]}節 {sec_name}")
            item_index_in_section = 0
            current_item = ""
            continue
            
        elif is_item:
            item_index_in_section += 1
            item_prefix = f"{chinese_nums[item_index_in_section-1]}、"
            current_item = f"{item_prefix}{text}"
            continue
            
        elif is_bullet:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if not lines:
                continue
            last_line = lines[-1]
            
            # Find dispatch number
            match = re.search(r'(\(\d+\)[^\s，、。]+字第\d+號(?:函|令)?)', last_line)
            if not match:
                match = re.search(r'([^\s，、。]+字第\d+號(?:函|令)?)', last_line)
                
            doc_id = match.group(1) if match else last_line
            doc_id = clean_doc_id(doc_id)
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
                new_entry = json.loads(json.dumps(db_entry))
                new_entry["分類索引"] = {
                    "章": "第三章 擬訂招標文件階段",
                    "節": current_section,
                    "項": current_item
                }
                extracted.append(new_entry)
            else:
                unmatched_count += 1
                placeholder_id = f"3-{unmatched_count:02d}"
                subject = lines[0]
                subject = re.sub(r'^主旨：', '', subject)
                content = "\n".join(lines)
                doc_date = extract_date(last_line)
                
                authority = "行政院公共工程委員會"
                for auth in ["內政部", "經濟部", "文化部", "法務部", "教育部", "原住民族委員會"]:
                    if auth in last_line:
                        authority = auth
                        break
                        
                new_entry = {
                    "項次": placeholder_id,
                    "分類索引": {
                        "章": "第三章 擬訂招標文件階段",
                        "節": current_section,
                        "項": current_item
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
                extracted.append(new_entry)
                
    return extracted, unmatched_count

def parse_new_version(docx_path, gpl_map):
    doc = docx.Document(docx_path)
    
    chinese_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", 
                    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十"]
    
    sections = [
        "確認採購類型", "確認採購金額", "擬定招標方式", "擬定決標原則", "廠商資格訂定",
        "技術規格訂定與同等品", "成立採購評選委員會", "擬訂投標須知",
        "擬訂評選項目、評審標準及評定方式", "擬訂採購價金及標單",
        "擬訂服務費用及價金之給付條件", "擬訂規範、圖說及履約期限",
        "擬訂契約草案", "招標文件公開閱覽", "其他招標文件事項"
    ]
    
    section_map = {}
    for idx, sec in enumerate(sections):
        section_map[sec] = f"第{chinese_nums[idx]}節 {sec}"
        
    # Custom mapping for Seventh Section
    section_map["採購評選委員會"] = "第七節 成立採購評選委員會"
        
    current_chapter = ""
    current_section = ""
    current_item = ""
    
    letters = []
    current_letter_lines = []
    
    def add_letter(lines):
        if not lines:
            return
        subject = ""
        for line in lines:
            if line.startswith("主旨："):
                subject = re.sub(r'^主旨：', '', line)
                break
        if not subject:
            subject = lines[0]
            
        last_line = lines[-1]
        match = re.search(r'(\(\d+\)[^\s，、。]+字第\d+號(?:函|令)?)', last_line)
        if not match:
            match = re.search(r'([^\s，、。]+字第\d+號(?:函|令)?)', last_line)
        doc_id = match.group(1) if match else last_line
        doc_id = clean_doc_id(doc_id)
        
        letters.append({
            "section": current_section,
            "item": current_item,
            "lines": lines,
            "doc_id": doc_id,
            "subject": subject,
            "last_line": last_line
        })

    dispatch_pattern = r'^[^\s，、。]+?(?:函|令)\s*\d+年\s*\d+月\s*\d+日?\s*[^\s，、。]*?字第\d+號'

    for i, p in enumerate(doc.paragraphs):
        text = p.text.strip()
        if not text:
            continue
            
        is_heading = (p.style.name == "List Paragraph")
        
        if is_heading:
            if re.search(r'^第三章\s+擬訂招標文件階段', text) or text == "第三章\t擬訂招標文件階段":
                current_chapter = text
                continue
            elif re.search(r'^第[一二三四五六七八九十]+節', text):
                sec_raw = re.sub(r'\s+', ' ', text)
                m = re.match(r'^第[一二三四五六七八九十]+節\s*(.*)', sec_raw)
                if m:
                    sec_core = m.group(1).strip()
                    current_section = section_map.get(sec_core, sec_raw)
                else:
                    current_section = sec_raw
                continue
            elif re.search(r'^[一二三四五六七八九十百]+[、\.]', text):
                item_raw = re.sub(r'\s+', ' ', text)
                current_item = item_raw
                continue
            
        p_lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not p_lines:
            continue
            
        if p_lines[0].startswith("主旨："):
            if current_letter_lines:
                add_letter(current_letter_lines)
                current_letter_lines = []
            
        current_letter_lines.extend(p_lines)
        
        last_line = p_lines[-1]
        if re.match(dispatch_pattern, last_line):
            add_letter(current_letter_lines)
            current_letter_lines = []
            
    if current_letter_lines:
        add_letter(current_letter_lines)
        
    new_extracted = []
    unmatched_count = 0
    
    for idx, l in enumerate(letters):
        std_doc_id = re.sub(r'\s+', '', l["doc_id"])
        
        matches = gpl_map.get(std_doc_id, [])
        if not matches:
            for k, v in gpl_map.items():
                if std_doc_id in k or k in std_doc_id:
                    matches = v
                    break
                    
        item_name = l["item"]
        
        if matches:
            db_entry = matches[0]
            new_entry = json.loads(json.dumps(db_entry))
            new_entry["分類索引"] = {
                "章": "第三章 擬訂招標文件階段",
                "節": l["section"],
                "項": item_name
            }
            new_extracted.append(new_entry)
        else:
            unmatched_count += 1
            placeholder_id = f"3-new-{unmatched_count:02d}"
            content = "\n".join(l["lines"])
            doc_date = extract_date(l["last_line"])
            
            authority = "行政院公共工程委員會"
            for auth in ["內政部", "經濟部", "文化部", "法務部", "教育部", "原住民族委員會"]:
                if auth in l["last_line"]:
                    authority = auth
                    break
                    
            new_entry = {
                "項次": placeholder_id,
                "分類索引": {
                    "章": "第三章 擬訂招標文件階段",
                    "節": l["section"],
                    "項": item_name
                },
                "發文機關": authority,
                "發文字號": l["doc_id"] + ("函" if not l["doc_id"].endswith(("函", "令")) else ""),
                "主題": l["subject"],
                "依據採購法條文": "",
                "上網日期": "",
                "發文日期": doc_date,
                "連結網址": "",
                "內容": content,
                "廢止或補充之備註": ""
            }
            new_extracted.append(new_entry)
            
    return new_extracted, unmatched_count

def main():
    docx_path_leader = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章_組長版.docx"
    docx_path_new = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章(112.1開始增加).docx"
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\gplAll_1150630.json"
    output_json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章.json"

    # Load master JSON database
    print(f"Loading database from {json_path}...")
    with open(json_path, "r", encoding="utf-8") as f:
        gpl_data = json.load(f)

    # Index by dispatch number
    gpl_map = {}
    for entry in gpl_data:
        doc_id = entry.get("發文字號", "").strip()
        if doc_id:
            std_id = re.sub(r'\s+', '', doc_id)
            gpl_map.setdefault(std_id, []).append(entry)

    # Parse documents
    print("Parsing third chapter leader version docx...")
    leader_entries, unmatched_leader = parse_leader_version(docx_path_leader, gpl_map)
    print(f"Leader Version completed. Extracted: {len(leader_entries)}, Unmatched: {unmatched_leader}")

    print("Parsing third chapter new 112.1 docx...")
    new_entries, unmatched_new = parse_new_version(docx_path_new, gpl_map)
    print(f"New Version completed. Extracted: {len(new_entries)}, Unmatched: {unmatched_new}")

    # Combine
    combined = leader_entries + new_entries
    print(f"Combined total entries: {len(combined)}")

    # Group by section order and sort internally
    chinese_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", 
                    "十一", "十二", "十三", "十四", "十五"]
    sections = [
        "確認採購類型", "確認採購金額", "擬定招標方式", "擬定決標原則", "廠商資格訂定",
        "技術規格訂定與同等品", "成立採購評選委員會", "擬訂投標須知",
        "擬訂評選項目、評審標準及評定方式", "擬訂採購價金及標單",
        "擬訂服務費用及價金之給付條件", "擬訂規範、圖說及履約期限",
        "擬訂契約草案", "招標文件公開閱覽", "其他招標文件事項"
    ]
    
    section_order = [f"第{chinese_nums[idx]}節 {sec}" for idx, sec in enumerate(sections)]
    
    groups = {sec: [] for sec in section_order}
    other_groups = {}
    
    for item in combined:
        sec = item.get("分類索引", {}).get("節", "")
        if sec in groups:
            groups[sec].append(item)
        else:
            other_groups.setdefault(sec, []).append(item)
            
    sorted_combined = []
    print("Sorting each section internally by 民國 date...")
    for sec in section_order:
        sec_items = groups[sec]
        sec_items.sort(key=get_date_val)
        sorted_combined.extend(sec_items)
        print(f"  {sec}: {len(sec_items)} items sorted.")
        
    for sec, sec_items in other_groups.items():
        sec_items.sort(key=get_date_val)
        sorted_combined.extend(sec_items)
        print(f"  Other Section '{sec}': {len(sec_items)} items sorted.")

    # Save to file
    print(f"Saving combined sorted Chapter 3 database to {output_json_path}...")
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_combined, f, ensure_ascii=False, indent=2)

    print("Chapter 3 Word to JSON processing completed successfully.")

if __name__ == "__main__":
    main()
