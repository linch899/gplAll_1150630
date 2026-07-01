---
name: typeset-pcc-letters-to-docx
description: Typesets government procurement interpretive letters from JSON to docx following the specific formatting guidelines of Chapter 1 (font, colors, line spacing, and precise hanging indents).
---

# Typeset PCC Letters to DOCX Skill

This skill allows you to format and export government procurement interpretive letters from a JSON database file (e.g. `第一章.json`) into a highly polished Microsoft Word document (`.docx`) that complies with standard governmental typesetting guidelines.

## Layout Specifications

- **Fonts**: Microsoft JhengHei (`微軟正黑體`) for headings and letter headers; PMingLiU (`新細明體`) for body text.
- **Sizes**: Document default is `12 pt`.
- **Colors**: Red (`FF0000`) for chapter, section, and subsection headings.
- **Line Spacing**: EXACTLY `24 pt` for headings.
- **Indents**: 
  - Standard headers/subjects/explanations: Left Indent `36 pt`, First Line Indent `-36 pt`.
  - Explanation list items (`一、`, `二、`): Left Indent `36 pt`, First Line Indent `-24 pt`.
  - Remark list items (`1.`, `2.`): Left Indent `48 pt`, first item First Line Indent `-48 pt`, subsequent items First Line Indent `-12 pt`.

## Usage

Run the Python export script located in the skill's scripts directory:

```bash
python .agents/skills/typeset_docx/scripts/export_docx.py --input <input_json> --output <output_docx> [--range <start_item>-<end_item>]
```

For example:
```bash
python .agents/skills/typeset_docx/scripts/export_docx.py --input "第一章/第一章.json" --output "第一章/第一章_排版後.docx"
```
