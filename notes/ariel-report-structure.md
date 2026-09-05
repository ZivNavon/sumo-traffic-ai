---
type: notes
project: Trafic AI
date: 2026-08-29
status: reference
tags: [final-report, template, reference]
---

# Ariel's Report — Structure Reference (96 points)

Project: Static Fourier-Transform Spectrometer for photonics lab.
Authors: Ariel Mazuz + Yuri Yakov Klein. Advisor: Prof. Boris Epter. Semester B, 2025.

## Structure (follow this for our final report)

### Front matter
- Cover: faculty, project title (Hebrew + English), authors + IDs, advisor, semester
- Acknowledgments (תודות): advisor, department, families
- Abstract (Hebrew תקציר + English Abstract) — 1 paragraph each
- List of figures (רשימת איורים)
- List of tables (רשימת טבלאות)
- List of formulas (רשימת נוסחאות)
- List of abbreviations (רשימת קיצורים)

### Body chapters
- **Chapter A — Introduction (מבוא לפרויקט)**
  - General background (רקע כללי)
  - Problem description (תיאור הבעיה)
  - Project goals (מטרת הפרויקט)
  - Report structure (מבנה ספר הפרויקט)

- **Chapter B — Theoretical Background & Literature (רקע תיאורטי וסקר ספרות)**
  - ~10–13 subsections, each covering one concept
  - Ends with a summary table of theory

- **Chapter C — Work Process (מהלך העבודה)**
  - Methodology (מתודולוגיה)
  - Implementation (מימוש): step-by-step development
  - Tool comparison (manual Excel vs automated Python)
  - Future expansion possibilities

- **Chapter D — Results (תוצאות)**
  - One section per experiment type
  - Graphs with captions matching רשימת איורים
  - Result summary table at end

- **Chapter E — Conclusions (מסקנות)**
  - Summary of findings
  - What worked, what didn't
  - Future directions
  - Comparison table (summary)

### Back matter
- Bibliography (ביבליוגרפיה) — numbered, with sources cited throughout
- Appendices (נספחים): datasheets, lab instructions for students, Python code

## Key formatting observations
- Chapter numbering: פרק א', פרק ב', ... (Hebrew letters)
- Subsection numbering: 1, 2, 3... (within each chapter)
- Tables: centered, titled above with number
- Figures: titled below with number matching רשימת איורים
- Formulas: numbered right-aligned in parentheses
- Callout boxes not used (but we use Obsidian callouts in our draft — convert to boxed text in Word)
- No em dashes — use commas and periods
- RTL document, David/Times New Roman font

## What made it 96 points (inferred)
- Complete theoretical foundation (13 subsections in Chapter B)
- Clear comparison table: static vs dynamic spectrometer
- Step-by-step development narrative with real problems encountered
- Results compared against commercial reference spectrometer
- Lab manual included as appendix (actual deliverable beyond the report)
- Appendices with full datasheets

## Application to our report
Our equivalent of the "reference spectrometer" comparison is the TIMER baseline.
Our equivalent of the "lab manual" deliverable is the sim/ codebase on GitHub.
Our unique contribution: multi-seed generalization analysis — stronger statistical rigor than a single-seed study.
