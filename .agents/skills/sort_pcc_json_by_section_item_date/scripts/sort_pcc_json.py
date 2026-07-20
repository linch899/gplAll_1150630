#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sort Government Procurement Interpretive Letter JSON Files
Multi-level sorting:
1. 分類索引.節 (Section Chinese numerals -> 1..15, empty -> 0)
2. 分類索引.項 (Item Chinese numerals -> 1..25, empty -> 0)
3. 發文日期 (ROC date string -> chronological value ascending)
"""

import sys
import json
import re
import os

chinese_num_map = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
    '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
    '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25
}

def parse_section_num(sec_str):
    if not sec_str:
        return 0
    m = re.match(r'^第([一二三四五六七八九十]+)節', sec_str.strip())
    if m:
        c_num = m.group(1)
        return chinese_num_map.get(c_num, 999)
    return 999

def parse_item_num(item_str):
    if not item_str:
        return 0
    m = re.match(r'^([一二三四五六七八九十]+)[、\.]', item_str.strip())
    if m:
        c_num = m.group(1)
        return chinese_num_map.get(c_num, 999)
    return 999

def get_date_val(date_str):
    if not date_str:
        return 0
    date_str = str(date_str).strip()
    if len(date_str) < 4:
        return 0
    try:
        year_str = date_str[:-4]
        month_str = date_str[-4:-2]
        day_str = date_str[-2:]
        return int(year_str) * 10000 + int(month_str) * 100 + int(day_str)
    except ValueError:
        return 0

def get_sort_key(entry):
    sec = entry.get("分類索引", {}).get("節", "")
    item = entry.get("分類索引", {}).get("項", "")
    date_str = entry.get("發文日期", "")
    
    sec_num = parse_section_num(sec)
    item_num = parse_item_num(item)
    date_num = get_date_val(date_str)
    
    return (sec_num, item_num, date_num)

def sort_pcc_json(json_path):
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Target file not found: {json_path}")
        
    print(f"[Sort Skill] Reading target file: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    # Independent calculation BEFORE sorting
    count_before = len(raw_data)
    print(f"[Sort Skill] Total entries BEFORE sorting: {count_before}")
    
    # Perform stable multi-level sort
    sorted_data = sorted(raw_data, key=get_sort_key)
    
    # Independent calculation AFTER sorting
    count_after = len(sorted_data)
    print(f"[Sort Skill] Total entries AFTER sorting: {count_after}")
    
    if count_before != count_after:
        raise ValueError(f"[Sort Skill] COUNT MISMATCH ERROR! Before: {count_before}, After: {count_after}")
        
    print(f"[Sort Skill] Writing sorted data back to {json_path}...")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, ensure_ascii=False, indent=2)
        
    print(f"[Sort Skill] Successfully sorted {count_after} entries.")
    return count_before, count_after

def main():
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        # Default fallback to Chapter 3 JSON if exists
        target_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章.json"
        
    sort_pcc_json(target_path)

if __name__ == "__main__":
    main()
