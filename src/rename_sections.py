import json
import os

def main():
    json_path = r"D:\AI Workplace\antigravity\1150630_政府採購解釋函令前置作業\第二章\第二章.json"

    if not os.path.exists(json_path):
        print(f"Error: file {json_path} not found.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Predefined Section Prefix Mapping
    mapping = {
        "投標須知": "第一節 投標須知",
        "工程採購契約": "第二節 工程採購契約",
        "財物採購契約": "第三節 財物採購契約",
        "勞務採購契約": "第四節 勞務採購契約",
        "聲明書": "第五節 聲明書",
        "切結書": "第六節 切結書",
        "其他招標相關文件或表格": "第七節 其他招標相關文件或表格"
    }

    modified_count = 0
    for item in data:
        current_sec = item.get("分類索引", {}).get("節", "")
        if current_sec in mapping:
            item["分類索引"]["節"] = mapping[current_sec]
            modified_count += 1
        elif current_sec.startswith(("第一節", "第二節", "第三節", "第四節", "第五節", "第六節", "第七節")):
            # Already mapped, skip
            pass
        else:
            print(f"Warning: Section '{current_sec}' not found in mapping.")

    # Save back to 第二章.json
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Successfully updated '節' fields. Modified: {modified_count} items. Total: {len(data)}")

if __name__ == "__main__":
    main()
