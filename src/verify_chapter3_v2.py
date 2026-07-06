import json
import os
import sys

def main():
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章.json"
    log_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第三章\第三章比對紀錄.txt"
    
    print("=== Verification v2 Start ===")
    if not os.path.exists(json_path):
        print(f"Error: {json_path} does not exist!")
        sys.exit(1)
    if not os.path.exists(log_path):
        print(f"Error: {log_path} does not exist!")
        sys.exit(1)
        
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"1. Total entries found: {len(data)}")
    if len(data) != 910:
        print(f"Error: Expected 910 entries, but found {len(data)}.")
        sys.exit(1)
    print("   -> PASS")
    
    # Check unmatched counts
    leader_placeholders = [item.get("項次") for item in data if item.get("項次", "").startswith("3-") and not item.get("項次", "").startswith("3-new")]
    new_placeholders = [item.get("項次") for item in data if item.get("項次", "").startswith("3-new-")]
    
    print(f"2. Unmatched placeholders in JSON:")
    print(f"   Leader unmatched count: {len(leader_placeholders)}")
    print(f"   New unmatched count: {len(new_placeholders)}")
    
    if len(leader_placeholders) != 77:
        print(f"Error: Expected 77 leader unmatched placeholders, found {len(leader_placeholders)}.")
        sys.exit(1)
    if len(new_placeholders) != 2:
        print(f"Error: Expected 2 new unmatched placeholders, found {len(new_placeholders)}.")
        sys.exit(1)
    print("   -> PASS")

    # Check database matching verification for 台90處忠六字第05815號
    # Let's search for the matched item for 台90處忠六字第05815號
    matched_05815 = [item for item in data if "05815" in item.get("發文字號", "")]
    print(f"3. Searching for 05815 matching:")
    if matched_05815:
        for m in matched_05815:
            print(f"   Matched entry: {m.get('發文字號')} | 項次: {m.get('項次')} | 分類索引: {m.get('分類索引')}")
    else:
        print("   Error: 05815 not found in JSON database!")
        sys.exit(1)
    print("   -> PASS")

    # Check database matching verification for 1120022327
    matched_22327 = [item for item in data if "1120022327" in item.get("發文字號", "")]
    print(f"4. Searching for 1120022327 matching:")
    if matched_22327:
        for m in matched_22327:
            print(f"   Matched entry: {m.get('發文字號')} | 項次: {m.get('項次')} | 分類索引: {m.get('分類索引')}")
    else:
        print("   Error: 1120022327 not found in JSON database!")
        sys.exit(1)
    print("   -> PASS")

    print("\n=== Verification v2 Successful: ALL TESTS PASSED! ===")

if __name__ == "__main__":
    main()
