---
type: reference
project: Trafic AI
tags: [report, requirements, final-project, bsc]
---

# Final Project Report Requirements — B.Sc. Electrical Engineering

Source: Faculty guidelines document (sections א, ב, ג, ט, יא, יב)

---

## Report Structure (Chapter by Chapter)

| Chapter | Content | Notes |
|---|---|---|
| Summary | Short abstract in Hebrew AND English | Required in both languages |
| TOC | Table of contents, list of abbreviations, list of figures, list of tables | |
| English Summary | Management summary in English | Separate from abstract |
| **Chapter 1** — Introduction | 2-3 pages. General background of the problem and solution. Short overview of report structure. | Keep concise |
| **Chapter 2** — Literature Review | Theoretical background relevant to the project. Findings from related materials. IEEE citation format throughout. | |
| **Chapter 3** — Methods and Materials | Detail the methods, models, systems, and algorithms used in the project. | Core technical chapter |
| **Chapter 4** — Results | Main results and their discussion. | Include comparison tables/graphs |
| **Chapter 5** — Summary and Conclusions | Summary of project progress and main conclusions. | |
| References | All sources cited in the report, IEEE format. | |
| Appendices | Data files not available online, supplementary material. | Code goes to GitHub, not here |

---

## Formatting Rules

- **Hebrew font:** David or Narkisim, size 12
- **English font:** Times New Roman, size 11
- **Line spacing:** Single
- **Text alignment:** Justified (two-sided)
- **Equations, figures, tables:** Must all be numbered. Source must appear below each table.
- **Submission:** Digital only.

---

## Code and Simulation

- Code and simulation files: shared via **GitHub only**.
- Data files accessible online: link only.
- Data files NOT accessible online: include as appendices or in digital format.

---

## Poster Requirements

Must show key points of the report in concise bullet-point form:
- Short background
- Methods and materials
- Results
- Conclusions

---

## Defense (Presentation)

- **Duration:** 20 minutes presentation + 10 minutes Q&A
- **Language:** English (both presentation content and project summary)
- **Two examiners** from the faculty per defense

### Presentation Slide Structure

| Slide # | Content |
|---|---|
| 1 | Cover: project title, student names, supervisor names |
| 2 | Project objective |
| 3-4 | Required theoretical background |
| 5 | Methods |
| 6-8 | Results, discussion, and analysis |
| 9 | Summary |
| 10 | Recommendations for continued research |

---

## Grading Breakdown

| Component | Weight |
|---|---|
| Progress report | 5% |
| Final report | 70% |
| Defense exam | 20% |
| Poster | 5% |

> Minimum passing grade: **60**. Below 60, the project is considered failed and the coordinator will guide next steps.

---

## General Project Rules (sections א-ג)

### Course basics
- 6 credit points, spans two semesters.
- Goal: apply engineering principles independently.
- Students must cooperate with supervisor, submit on time, present at faculty events.

### Team
- Projects done in pairs by default. Coordinator can approve solo or 3-person teams.
- Students are ultimately responsible for execution. Each member must have equal contribution and full understanding of the entire project.

### AI Tools Rule (CRITICAL for this project)
> Rule 8: Use of AI tools (LLMs and others) is **permitted**. However, students must declare this use and demonstrate **full mastery** of every step where AI was involved. In the report and defense, students must be able to explain exactly what the AI did and to what extent it influenced the result.

**What this means for us:** Using Claude to help write code is fine, but you must be able to explain every line of the DQN, every design decision, every parameter choice. Never put code in the project you cannot defend in the exam.

### Project core (rule 7)
The core of the project is: research or application implemented within the project framework, including models and/or algorithms, presentation of results, conclusions, and summary. This is exactly what TIMER vs SCRIPT vs DQN delivers.

---

## Key Implications for This Project

- Chapter 3 (Methods): describe SUMO, TraCI, TIMER/SCRIPT/DQN controllers, network design, state representation, reward function.
- Chapter 4 (Results): comparison tables TIMER vs SCRIPT vs DQN across both scenarios. Include training reward curve for DQN.
- Chapter 2 (Literature): cite papers on RL for traffic signal control, DQN (Mnih et al. 2015), SUMO documentation.
- GitHub: `https://github.com/ZivNavon/sumo-traffic-ai` — keep it clean and updated.
- Report language: Hebrew or English (student's choice).
