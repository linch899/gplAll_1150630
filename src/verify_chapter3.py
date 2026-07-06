import json
import os
import sys

def get_date_val(item):
    date_str = item.get("發文日期", "").strip()
    if not date_str:
        return 0
    if len(date_str) < 4:
        return 0
    try:
        year_str = date_str[:-4]
        month_str = date_str[-4:-2]
        day_str = date_str[-2:]
        return int(year_str) * 10000 + int(month_str) * 100 + int(day_str)
    except ValueError:
        return 0

def main():
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章.json"
    
    print("=== Verification Start ===")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist!")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"1. Total entries found: {len(data)}")
    if len(data) != 910:
        print(f"Error: Expected 910 entries, but found {len(data)}.")
        sys.exit(1)
    else:
        print("   -> PASS")
        
    # Check chapter
    print("2. Verifying chapter names...")
    bad_chapters = [item for item in data if item.get("分類索引", {}).get("章", "") != "第三章 擬訂招標文件階段"]
    if bad_chapters:
        print(f"Error: Found {len(bad_chapters)} items with incorrect chapter name!")
        sys.exit(1)
    else:
        print("   -> PASS")
        
    # Check sections
    print("3. Verifying section names...")
    chinese_nums = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", 
                    "十一", "十二", "十三", "十四", "十五"]
    sections = [
        "確認採購類型", "確認採購金額", "擬定招標方式", "擬定決標原則", "廠商資格訂定",
        "技術規格訂定與同等品", "成立採購評選委員會", "擬訂投標須知",
        "擬訂評選項目、評審標準及評定方式", "擬訂採購價金及標單",
        "擬訂服務費用及價金之給付條件", "擬訂規範、圖說及履約期限",
        "擬訂契約草案", "招標文件公開閱覽", "其他招標文件事項"
    ]
    expected_sections = [f"第{chinese_nums[idx]}節 {sec}" for idx, sec in enumerate(sections)]
    
    unique_sections = set(item.get("分類索引", {}).get("節", "") for item in data)
    print(f"   Found {len(unique_sections)} unique sections.")
    
    invalid_sections = unique_sections - set(expected_sections)
    if invalid_sections:
        print(f"Error: Found invalid section names: {invalid_sections}")
        sys.exit(1)
    else:
        print("   -> PASS")
        
    # Check chronological sorting
    print("4. Verifying chronological sorting in each section...")
    section_items = {sec: [] for sec in expected_sections}
    for item in data:
        sec = item.get("分類索引", {}).get("節", "")
        section_items[sec].append(item)
        
    sorting_errors = 0
    for sec, items in section_items.items():
        for idx in range(1, len(items)):
            prev_val = get_date_val(items[idx-1])
            curr_val = get_date_val(items[idx])
            if prev_val > curr_val:
                print(f"Error in {sec} sorting: Item {idx-1} date '{items[idx-1].get('發文日期')}' > Item {idx} date '{items[idx].get('發文日期')}'")
                sorting_errors += 1
                
    if sorting_errors > 0:
        print(f"Error: Found {sorting_errors} sorting issues!")
        sys.exit(1)
    else:
        print("   -> PASS")
        
    # Check unmatched placeholders
    print("5. Verifying unmatched placeholders...")
    leader_placeholders = [item.get("項次") for item in data if item.get("項次", "").startswith("3-") and not item.get("項次", "").startswith("3-new")]
    new_placeholders = [item.get("項次") for item in data if item.get("項次", "").startswith("3-new-")]
    
    print(f"   Leader version unmatched placeholders count: {len(leader_placeholders)}")
    print(f"   New version unmatched placeholders count: {len(new_placeholders)}")
    if len(leader_placeholders) != 90:
        print(f"Error: Expected 90 leader unmatched placeholders, found {len(leader_placeholders)}.")
        sys.exit(1)
    if len(new_placeholders) != 3:
        print(f"Error: Expected 3 new unmatched placeholders, found {len(new_placeholders)}.")
        sys.exit(1)
    print("   -> PASS")

    print("\n=== Verification Successful: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
