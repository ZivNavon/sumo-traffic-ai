# Adaptable project-book structure

Use this reference when planning or editing a long academic or technical project document. It captures reusable document architecture only. Never copy wording, results, citations, acknowledgements, or project-specific content from a reference report.

The institution's instructions and the project's actual evidence take precedence. Include a section only when it serves the reader or is required.

## Front matter

1. **Cover page (שער)** — institution, project type, title in the required languages, authors, supervisor, and submission term.
2. **Table of contents (תוכן עניינים)** — generated from heading styles after the structure is stable.
3. **Acknowledgements (תודות)** — optional and personal; write from information supplied by the authors. Never infer names or contributions.
4. **Abstract or summary (תקציר)** — problem, approach, principal evidence, main result, and limitations in compact form.
5. **English abstract** — include only when required. It should accurately mirror the approved Hebrew abstract, not introduce new claims.
6. **Lists of figures, tables, and equations (רשימת איורים, טבלאות ונוסחאות)** — include only categories used often enough to justify a list.
7. **Abbreviations and symbols (רשימת קיצורים וסימנים)** — define only terms actually used in the document.

## Main body

### 1. Introduction (מבוא)

- **Background (רקע כללי):** only the context needed to understand the project.
- **Problem statement (תיאור הבעיה):** the concrete gap, need, or question.
- **Objectives and scope (מטרות ותחום הפרויקט):** what the project set out to do, including boundaries and success criteria when known.
- **Document roadmap (מבנה הספר):** optional; keep it to one short paragraph.

Do not place the full literature review or technical explanation here. Preview later material briefly.

### 2. Technical background and related work (רקע תיאורטי וסקר ספרות)

- Define the concepts and mechanisms needed for the work.
- Organize by concept or decision dependency, not source-by-source summaries.
- Compare relevant approaches and explain why they matter to this project.
- Cite factual and borrowed material at the point of use.
- End with the specific gap, constraints, or design implications carried into the project.

Do not repeat the introduction's motivation. This chapter explains what the reader must know, not what the project accomplished.

### 3. Methodology and implementation (מתודולוגיה ומימוש)

Separate the reasoning from the build when that improves clarity:

- **Methodology:** assumptions, inputs, procedure, processing or analysis stages, evaluation criteria, limitations, and sources of error.
- **Design and implementation:** architecture, components, tools, major design decisions, and the final workflow.
- **Development path:** include prototypes, failed attempts, or tool comparisons only when they explain a decision or limitation.
- **Validation plan:** state how outputs will be checked before presenting the results.

Describe the final method in the main narrative. Move exhaustive code, configurations, screenshots, and vendor material to appendices.

### 4. Results (תוצאות)

Present evidence in the order needed to answer the objectives:

- calibration or sanity checks;
- primary experiments or measurements;
- comparisons with references, baselines, or expected values;
- tables and figures with readable labels and units;
- uncertainty, anomalies, failed cases, and missing evidence.

Text near a figure or table should state the important pattern and its relevance. It should not narrate every visible value. Keep observations here; reserve broader meaning for the discussion or conclusions unless the required format combines them.

### 5. Discussion and conclusions (דיון ומסקנות)

- Answer each objective using the evidence already shown.
- Distinguish measured results from interpretation.
- Explain discrepancies, limitations, and threats to validity.
- State what the project demonstrates and what it does not demonstrate.
- Suggest future work only when it follows from a documented limitation or result.

Do not restate the abstract, introduction, and results chapter paragraph by paragraph.

### 6. References (ביבליוגרפיה)

Use one required citation style consistently. Every listed source should be cited in the text, and every in-text citation should resolve to a listed source. Never fabricate missing bibliographic details.

### 7. Appendices (נספחים)

Use appendices for material that supports verification but interrupts the main argument, such as:

- detailed calculations or additional results;
- full questionnaires, protocols, or lab instructions;
- code listings or repository notes;
- component specifications and datasheets;
- supplementary figures and tables.

Refer to each useful appendix from the main text. Do not use appendices as storage for unrelated material.

## Ownership map for repeated ideas

Assign one canonical home before editing:

| Idea | Full treatment belongs in | Elsewhere |
| --- | --- | --- |
| Why the project matters | Introduction | One-sentence context in abstract and conclusion |
| Theory and prior work | Background | Brief references where a method depends on it |
| What was done | Methodology and implementation | Compact approach summary in abstract |
| What was observed | Results | Only the decisive values in abstract and conclusions |
| What the evidence means | Discussion and conclusions | Short local interpretation beside results when necessary |
| Limitations | Methodology for known constraints; discussion for observed effects | Compact qualification in abstract if it changes the main claim |
| Future work | Conclusions | Mention earlier only when it defines current scope |

## Planning checks

Before drafting or restructuring:

1. Read the assignment or department template if available.
2. Inventory the supplied evidence and mark unsupported claims.
3. Build a one-line purpose statement for every proposed section.
4. Remove sections whose purpose duplicates another section.
5. Assign each recurring idea a canonical home using the ownership map.
6. Draft from evidence outward; never fill a template with invented content.

After editing, read the headings as a standalone outline. Then read the opening and closing paragraph of every chapter in sequence to catch repeated introductions, repeated conclusions, and broken transitions.
