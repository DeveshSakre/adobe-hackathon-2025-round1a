# adobe-hackathon-2025-round1a
Submission for Adobe India Hackathon 2025 – Round 1A: PDF Outline Extractor using PyMuPDF and Docker.

#  Adobe India Hackathon 2025 – Round 1A

**Challenge:** Connecting the Dots – Understand Your Document  
**Task:** Automatically extract structured outlines (Title, H1, H2, H3) from PDF files.

---

## 📘 Overview

This project processes PDF files and outputs a structured `JSON` outline containing:
- Document title
- Section headings (H1, H2, H3) with level and page number

The solution is built using:
-  Python 3.9
-  PyMuPDF (`fitz`) for PDF parsing
-  Docker for portability and offline execution

---

##  Approach

We approach this challenge with a modular pipeline:

### 1. **Text Extraction**
- The PDF is parsed using `PyMuPDF`, extracting blocks, lines, and spans.
- Each span is captured with its font size, flags, coordinates, and page metadata.

### 2. **Line Grouping**
- Spans are grouped into lines based on vertical alignment (`y_tol`) and similar font size.
- This reconstructs readable horizontal lines from fragmented text boxes.

### 3. **Title Detection**
- We detect the **title** using the **largest font size** within the first page.
- Additional heuristics like page width coverage and presence of title-related keywords are used.
- Multi-line titles are merged if they share similar font sizes and appear consecutively.

### 4. **Heading Candidate Detection**
- Filters out lines that are:
  - Too short or long
  - Repeated across pages (headers/footers)
  - Not semantically meaningful (punctuation/numbers only)
- Retains headings that are either bold, large-font, or fully uppercase.

### 5. **Heading Level Assignment**
- Unique font sizes among headings are ranked descending.
- Top font size is assigned `H1`, next `H2`, and so on.
- Headings are grouped by their assigned level and page number.

### 6. **Final JSON Output**
Each `.pdf` file generates a `.json` with the format:

```json
{
  "title": "Sample Document Title",
  "outline": [
    { "level": "H1", "text": "Introduction", "page": 1 },
    { "level": "H2", "text": "Background", "page": 2 },
    { "level": "H3", "text": "Details", "page": 3 }
  ]
}
