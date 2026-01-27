import pdfplumber
import json
import os
import glob
import zipfile
import re
from operator import itemgetter
from lxml import etree
from typing import Dict, List, Any, Optional

# =========================
# Word(OpenXML) 네임스페이스
# =========================
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "v": "urn:schemas-microsoft-com:vml",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

class UniversalParser:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    # ---------------------------------------------------------
    # 공통 유틸리티
    # ---------------------------------------------------------
    def _save_json(self, data: Any, filename: str):
        path = os.path.join(self.output_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    # ---------------------------------------------------------
    # PDF 파싱 로직
    # ---------------------------------------------------------
    def _filter_overlapping_tables(self, tables):
        if not tables: return []
        indices_to_remove = set()
        for i, outer in enumerate(tables):
            outer_bbox = outer.bbox
            for j, inner in enumerate(tables):
                if i == j: continue
                inner_bbox = inner.bbox
                if (outer_bbox[0] <= inner_bbox[0] + 1 and
                    outer_bbox[1] <= inner_bbox[1] + 1 and
                    outer_bbox[2] >= inner_bbox[2] - 1 and
                    outer_bbox[3] >= inner_bbox[3] - 1):
                    indices_to_remove.add(i)
                    break
        return [t for i, t in enumerate(tables) if i not in indices_to_remove]

    def _is_inside_bbox(self, word, bboxes):
        w_center_x = (word['x0'] + word['x1']) / 2
        w_center_y = (word['top'] + word['bottom']) / 2
        for bbox in bboxes:
            if (bbox[0] <= w_center_x <= bbox[2]) and (bbox[1] <= w_center_y <= bbox[3]):
                return True
        return False

    def _table_to_markdown(self, table_data):
        if not table_data: return ""
        lines = []
        for row in table_data:
            cleaned_row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
            lines.append("| " + " | ".join(cleaned_row) + " |")
        return "\n".join(lines)

    def parse_pdf(self, pdf_path: str) -> List[Dict]:
        doc_data = []
        doc_id = os.path.basename(pdf_path)
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                raw_tables = page.find_tables()
                tables = self._filter_overlapping_tables(raw_tables)
                table_bboxes = [t.bbox for t in tables]
                page_contents = []

                # Table 처리
                for table in tables:
                    extracted_data = table.extract()
                    if not extracted_data: continue
                    
                    if len(extracted_data) == 1 and len(extracted_data[0]) == 1:
                        text_content = str(extracted_data[0][0]).strip().replace('\n', ' ')
                        if text_content:
                            page_contents.append({"type": "text", "top": table.bbox[1], "text": text_content})
                    else:
                        md_table = self._table_to_markdown(extracted_data)
                        if md_table:
                            page_contents.append({
                                "type": "table", 
                                "top": table.bbox[1], 
                                "text": f"\n[TABLE START]\n{md_table}\n[TABLE END]"
                            })

                # Image 처리
                for img in page.images:
                    if img['height'] > 10 and img['width'] > 10:
                        page_contents.append({
                            "type": "image", "top": img['top'], "text": "\n[IMAGE: 그림/도표/이미지 포함됨]\n"
                        })

                # Text 처리
                words = page.extract_words()
                words_outside = [w for w in words if not self._is_inside_bbox(w, table_bboxes)]
                
                if words_outside:
                    words_outside.sort(key=itemgetter("top", "x0"))
                    lines = []
                    if words_outside:
                        curr_line = [words_outside[0]]
                        for i in range(1, len(words_outside)):
                            if abs(words_outside[i]["top"] - words_outside[i-1]["top"]) < 5:
                                curr_line.append(words_outside[i])
                            else:
                                lines.append(curr_line)
                                curr_line = [words_outside[i]]
                        lines.append(curr_line)

                    for line in lines:
                        merged = " ".join([w["text"] for w in line]).strip()
                        if merged:
                            page_contents.append({"type": "text", "top": line[0]["top"], "text": merged})

                page_contents.sort(key=itemgetter("top"))
                doc_data.append({
                    "doc_id": doc_id,
                    "page_index": page_idx,
                    "texts": [item["text"] for item in page_contents]
                })
        return doc_data

    # ---------------------------------------------------------
    # Word 파싱 로직
    # ---------------------------------------------------------
    def _read_xml(self, z, path):
        return etree.fromstring(z.read(path))

    def parse_docx(self, docx_path: str) -> Dict:
        media_dir = os.path.join(self.output_dir, "media")
        os.makedirs(media_dir, exist_ok=True)
        
        with zipfile.ZipFile(docx_path) as z:
            if "word/document.xml" not in z.namelist():
                return {"error": "Invalid docx"}

            doc_root = self._read_xml(z, "word/document.xml")
            
            # Relationships
            rid_to_target = {}
            rels_path = "word/_rels/document.xml.rels"
            if rels_path in z.namelist():
                rel_root = self._read_xml(z, rels_path)
                for rel in rel_root.findall("rel:Relationship", namespaces=NS):
                    rid_to_target[rel.get("Id")] = rel.get("Target")

            body = doc_root.find(".//w:body", namespaces=NS)
            blocks = []
            img_counter = 0

            for child in body:
                tag = etree.QName(child).localname
                if tag == "p":
                    # Text
                    text = "".join([t.text for t in child.findall(".//w:t", namespaces=NS) if t.text]).strip()
                    if text: blocks.append({"type": "paragraph", "text": text})
                    
                    # Textbox
                    for tb_node in [".//w:pict//v:textbox//w:t", ".//w:drawing//a:t", ".//wps:txbx//w:t"]:
                        tb_text = "".join([t.text for t in child.findall(tb_node, namespaces=NS) if t.text]).strip()
                        if tb_text: blocks.append({"type": "textbox", "text": tb_text})

                    # Images
                    for blip in child.findall(".//a:blip", namespaces=NS):
                        rid = blip.get(f"{{{NS['r']}}}embed")
                        if rid and rid in rid_to_target:
                            img_counter += 1
                            target = rid_to_target[rid]
                            img_path = target if target.startswith("word/") else f"word/{target}"
                            if img_path in z.namelist():
                                out_name = f"{img_counter:04d}_{os.path.basename(img_path)}"
                                with open(os.path.join(media_dir, out_name), "wb") as f:
                                    f.write(z.read(img_path))
                                blocks.append({"type": "image", "saved_as": out_name})

                elif tag == "tbl":
                    rows = []
                    for tr in child.findall(".//w:tr", namespaces=NS):
                        row = ["".join([t.text for t in tc.findall(".//w:t", namespaces=NS) if t.text]).strip() 
                               for tc in tr.findall(".//w:tc", namespaces=NS)]
                        rows.append(row)
                    blocks.append({"type": "table", "rows": rows})

            return {"source": os.path.basename(docx_path), "blocks": blocks}

    # ---------------------------------------------------------
    # 통합 실행 함수
    # ---------------------------------------------------------
    def process_file(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        filename_no_ext = os.path.splitext(os.path.basename(file_path))[0]
        
        print(f"[*] Processing: {file_path}")
        
        if ext == ".pdf":
            result = self.parse_pdf(file_path)
            return self._save_json(result, f"{filename_no_ext}_pdf.json")
        elif ext == ".docx":
            result = self.parse_docx(file_path)
            return self._save_json(result, f"{filename_no_ext}_docx.json")
        else:
            print(f"[!] Unsupported extension: {ext}")
            return None