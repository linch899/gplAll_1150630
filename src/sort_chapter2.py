import json
import os

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
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第二章\第二章.json"

    if not os.path.exists(json_path):
        print(f"Error: file {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} items to sort.")

    # Section ordering
    section_order = [
        "投標須知",
        "工程採購契約",
        "財物採購契約",
        "勞務採購契約",
        "聲明書",
        "切結書",
        "其他招標相關文件或表格"
    ]

    # Group by section
    groups = {sec: [] for sec in section_order}
    other_groups = {} # For any unexpected sections

    for item in data:
        sec = item.get("分類索引", {}).get("節", "")
        if sec in groups:
            groups[sec].append(item)
        else:
            other_groups.setdefault(sec, []).append(item)

    # Sort each group chronologically by date
    sorted_data = []
    
    # 1. Add predefined sections in order, sorted internally
    for sec in section_order:
        sec_items = groups[sec]
        # Sort internally by date (oldest to newest)
        sec_items.sort(key=get_date_val)
        sorted_data.extend(sec_items)
        print(f"Section '{sec}': {len(sec_items)} items sorted.")

    # 2. Add other sections if any
    for sec, sec_items in other_groups.items():
        sec_items.sort(key=get_date_val)
        sorted_data.extend(sec_items)
        print(f"Other Section '{sec}': {len(sec_items)} items sorted.")

    # Save back to 第二章.json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully sorted and saved {len(sorted_data)} items.")

if __name__ == "__main__":
    main()
