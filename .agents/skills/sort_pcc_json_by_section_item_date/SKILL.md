---
name: sort_pcc_json_by_section_item_date
description: Multi-level sort government procurement interpretive letter JSON files by section (節), item (項), and dispatch date (發文日期), with independent before/after count verification.
---

# Sort PCC Interpretive Letter JSON Files Skill

Use this skill whenever you need to sort government procurement interpretive letter JSON files (such as `第一章.json`, `第二章.json`, `第三章.json`, etc.) according to the standardized multi-level ordering rules and report independent count calculations before and after sorting.

## Sorting Hierarchy

The sorting process follows a strict 3-level hierarchy:

1. **Level 1: Section (`分類索引.節`)**
   - Chinese section numerals (e.g. `第一節`, `第二節`, ..., `第十五節`) are converted to numerical values (1, 2, ..., 15) and sorted in ascending order.
   - Entries with an empty section (`""`) are assigned value `0` and placed at the very beginning.

2. **Level 2: Item (`分類索引.項`)**
   - Within the same section, Chinese item numerals (e.g. `一、`, `二、`, ..., `二十五、`) are converted to numerical values (1, 2, ..., 25) and sorted in ascending order.
   - Entries with an empty item (`""`) are assigned value `0` and placed before `一、`.

3. **Level 3: Dispatch Date (`發文日期`)**
   - Within the same section and item (or when item is empty), entries are sorted chronologically from oldest to newest ("由先到後").
   - ROC date strings (e.g. `"880714"`, `"1000125"`, `"1120104"`) are converted into integer date values (`year * 10000 + month * 100 + day`) for accurate ascending sorting.

## Key Rules & Integrity Guarantees

- **Data Integrity**: All item contents and fields remain strictly unchanged; only item ordering is modified.
- **Independent Counting**: The total entry count is calculated independently before sorting and after sorting.
- **Count Verification**: The process validates that `count_before == count_after` and reports both figures to the user.

## Execution

To sort a target JSON file, run the script provided in `scripts/`:

```bash
python .agents/skills/sort_pcc_json_by_section_item_date/scripts/sort_pcc_json.py "<path_to_target_json>"
```

### Example Usage

Sort Chapter 3 JSON file:
```bash
python .agents/skills/sort_pcc_json_by_section_item_date/scripts/sort_pcc_json.py "D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章.json"
```

## Workflow

1. **Locate Target File**: Identify the absolute or workspace-relative path of the target JSON file.
2. **Execute Script**: Run `sort_pcc_json.py` with the target path.
3. **Verify Output**: Confirm that count before and count after match, and that the sorting hierarchy is satisfied.
4. **Git Synchronization**: Per workspace rules, automatically run `git add`, `git commit`, and `git push`.
