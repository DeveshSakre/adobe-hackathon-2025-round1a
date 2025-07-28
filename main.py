import fitz  # PyMuPDF
import os
import json
import re
import statistics
import collections

INPUT_DIR = "input"
OUTPUT_DIR = "output"

# ------------------ regex & constants ------------------
WS_RE = re.compile(r"\s+")
ONLY_PUNCT_NUM = re.compile(r"^[\W\d_]+$", re.UNICODE)
SECTION_NUM_RE = re.compile(r"^\d+(\.\d+)*\b")
BULLET_CHARS = "•*-·◦●"

TITLE_HINT_WORDS = {
    "application", "form", "grant", "ltc", "overview", "foundation", "extension",
    "proposal", "rfp", "business", "plan", "library", "pathways", "parsippany", "troy", "hills"
}
FORM_KEYWORDS = ["name", "signature", "designation", "relationship", "pay", "age", "date", "servant"]

# -------------------------------------------------------
def clean_text(t):
    t = t.replace("\n", " ").strip()
    t = re.sub(rf"^[{re.escape(BULLET_CHARS)}\s]+", "", t)
    return WS_RE.sub(" ", t).strip()

def base_checks(t, max_words=40, max_len=200):
    if not t or ONLY_PUNCT_NUM.match(t):
        return False
    wc = len(t.split())
    if wc < 1 or wc > max_words:
        return False
    if len(t) > max_len:
        return False
    return True

# -------------------------------------------------------
def collect_segments(doc):
    segs = []
    for pno, page in enumerate(doc):
        pw, ph = page.rect.width, page.rect.height
        d = page.get_text("dict")
        for b in d["blocks"]:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    txt = s["text"].strip()
                    if not txt:
                        continue
                    x0, y0, x1, y1 = s["bbox"]
                    segs.append({
                        "page": pno,
                        "text": txt,
                        "font": s["size"],
                        "flags": s["flags"],
                        "x": x0,
                        "y": y0,
                        "width": x1 - x0,
                        "page_w": pw,
                        "page_h": ph,
                    })
    return segs

def group_segments_to_lines(segs, y_tol=3.0, font_tol=1.0):
    segs = sorted(segs, key=lambda s: (s["page"], s["y"], s["x"]))
    lines = []
    cur = None
    for s in segs:
        if cur is None:
            cur = [s]
            continue
        last = cur[-1]
        if (
            s["page"] == last["page"]
            and abs(s["y"] - last["y"]) <= y_tol
            and abs(s["font"] - last["font"]) <= font_tol
        ):
            cur.append(s)
        else:
            lines.append(_finalize_line(cur))
            cur = [s]
    if cur:
        lines.append(_finalize_line(cur))
    return lines

def _finalize_line(seg_group):
    text = clean_text(" ".join(s["text"] for s in seg_group))
    font = max(s["font"] for s in seg_group)
    flags_or = 0
    for s in seg_group:
        flags_or |= s["flags"]
    x0 = min(s["x"] for s in seg_group)
    x1 = max(s["x"] + s["width"] for s in seg_group)
    y0 = min(s["y"] for s in seg_group)
    page = seg_group[0]["page"]
    pw = seg_group[0]["page_w"]
    ph = seg_group[0]["page_h"]
    return {
        "page": page,
        "text": text,
        "font": font,
        "is_bold": bool(flags_or & 2),
        "x": x0,
        "y": y0,
        "width": x1 - x0,
        "page_w": pw,
        "page_h": ph,
    }

# -------------------------------------------------------
def has_title_hint(t):
    words = {w.strip('.,:;()').lower() for w in t.split()}
    return bool(words & TITLE_HINT_WORDS)

def detect_title(lines):
    cand_idx = None
    biggest_font = 0
    for i, ln in enumerate(lines):
        if ln["page"] > 1:
            break
        t = ln["text"]
        if not base_checks(t): continue
        if ln["width"] / ln["page_w"] < 0.25 and not has_title_hint(t):
            continue
        if ln["font"] > biggest_font:
            biggest_font = ln["font"]
            cand_idx = i
    if cand_idx is None:
        return None

    base = lines[cand_idx]
    parts = [base["text"]]
    page = base["page"]
    for ln in lines[cand_idx + 1:]:
        if ln["page"] != page:
            break
        if ln["font"] >= base["font"] * 0.9:
            parts.append(ln["text"])
    merged = clean_text(" ".join(parts))
    title = dict(base)
    title["text"] = merged
    return title

# -------------------------------------------------------
def detect_repeated(lines, min_frac=0.4):
    pages = max((ln["page"] for ln in lines), default=-1) + 1
    if pages <= 1: return set()
    counts = collections.Counter()
    seen = collections.defaultdict(set)
    for ln in lines:
        key = ln["text"].lower()
        if key in seen[ln["page"]]:
            continue
        seen[ln["page"]].add(key)
        counts[key] += 1
    return {k for k, v in counts.items() if v >= pages * min_frac}

# -------------------------------------------------------
def heading_candidates(lines, title):
    body_fonts = [ln["font"] for ln in lines if ln["text"]]
    body_med = statistics.median(body_fonts) if body_fonts else 12.0
    repeated = detect_repeated(lines)
    cands = []
    for ln in lines:
        t = ln["text"]
        if title and ln["page"] == title["page"] and t == title["text"]:
            continue
        if t.lower() in repeated:
            continue
        if not base_checks(t):
            continue
        if len(t) < 3:
            continue
        if ln["font"] >= body_med * 1.25 or t.isupper():
            cands.append(ln)
    return cands, body_med

# -------------------------------------------------------
def assign_levels(cands, title):
    # Assign heading levels dynamically by font size (bigger = higher)
    font_sizes = sorted({c['font'] for c in cands}, reverse=True)
    font_to_level = {}
    for i, size in enumerate(font_sizes):
        font_to_level[size] = f"H{i+1}"
    outline = []
    for c in sorted(cands, key=lambda x: (x["page"], x["y"])):
        level = font_to_level.get(c['font'], "H1")
        outline.append({"level": level, "text": c["text"], "page": c["page"]})
    return {"title": title["text"] if title else "", "outline": outline}

# -------------------------------------------------------
def process_pdf(path):
    try:
        doc = fitz.open(path)
        segs = collect_segments(doc)
        lines = group_segments_to_lines(segs)
        title = detect_title(lines)
        cands, _ = heading_candidates(lines, title)
        return assign_levels(cands, title)
    except Exception as e:
        print(f"ERROR processing {path}: {e}")
        return {"error": str(e), "file": path}

def process_pdfs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    for i, fname in enumerate(pdf_files):
        print(f"Processing {i+1}/{len(pdf_files)}: {fname}")
        result = process_pdf(os.path.join(INPUT_DIR, fname))
        out_path = os.path.join(OUTPUT_DIR, os.path.splitext(fname)[0] + ".json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=4)
    print("Processing complete. Results saved to 'output/'.")

if __name__ == "__main__":
    process_pdfs()