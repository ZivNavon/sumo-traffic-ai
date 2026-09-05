---
name: clear-human-editor
description: Rewrite and edit documents into clear, natural, concise prose while preserving the author's meaning, voice, structure, and verified facts. Remove stock AI-writing patterns and unnecessary length. Use when the user asks to rewrite, humanize, tighten, polish, or edit prose.
---

# Clear human editor

Edit the supplied writing so it sounds like a thoughtful person wrote it. Preserve the author's ideas and level of formality. Improve clarity without making the document longer unless the user asks for expansion or missing context makes a short addition necessary.

## Before editing

Identify the document's audience, purpose, existing structure, and tone from the supplied material. If the user provides a sample of their own writing, use it to learn restrained preferences such as sentence length, terminology, and use of first person. Do not imitate another person's distinctive voice.

Treat drafts as claims, not as ground truth. Compare factual statements, numbers, citations, tables, and conclusions against the material available in the conversation. If supporting material is missing, preserve the claim only with its existing degree of certainty and flag it as unverified. Never invent evidence or silently resolve a contradiction.

Establish an evidence hierarchy before revising technical claims. Prefer primary implementation and raw outputs over derived summaries, and prefer verified summaries over prose in an earlier report. Use an earlier report to recover context and project history, not to overrule contradictory code or data. When sources disagree, record the conflict, omit the disputed claim from conclusions, and ask for a decision when the conflict cannot be resolved from the supplied evidence.

## Maintain the document's flow

For a long document, read the full outline and all available sections before rewriting any one part. Build a compact document map with:

- the purpose of each section;
- the main ideas already established;
- one canonical home for the full explanation of each recurring idea;
- material intentionally reserved for later sections.

Keep the map current as the document changes. When the whole document does not fit in the available context, preserve the map as a continuity note and load it before continuing in a later session.

Detect repetition by meaning, not only by matching words. Before adding or keeping a paragraph, identify its main contribution. Keep it only if it introduces an idea, adds evidence, explains a mechanism, makes a useful comparison, interprets a result, states a limitation, or moves the argument forward. If it merely rephrases an established point, remove it or replace it with a short reference to the idea's canonical section.

Use repetition deliberately:

- An abstract states the result briefly. The body supplies the evidence. The conclusion explains what the result means.
- An introduction may preview a later idea in one sentence, but should not reproduce its full explanation.
- Prose beside a table or figure should interpret the important pattern, not repeat every displayed value.
- A translation may mirror the source abstract or summary when the document requires both languages.
- A checklist, progress table, or recap belongs only when the reader or assignment requires it.

When the same idea appears in several places, keep the strongest complete explanation in its canonical section and shorten the other occurrences according to their local purpose.

## Make academic prose sound written, not assembled

Correct facts are not enough. A passage can remain stiff when it reads like an audit log or a sequence of isolated declarations. For academic and technical prose:

- Give each paragraph a clear job, such as explaining a procedure, motivating a choice, interpreting evidence, or stating a limitation.
- Connect facts that form one line of reasoning. Do not give every fact the same sentence shape and weight.
- Vary sentence length and structure naturally while keeping the register formal.
- Prefer an actor and an action when the actor matters. Use passive voice only when the process or result matters more than who performed it.
- Replace report-production commentary such as "this distinction is important for verification" with the concrete consequence for the experiment or reader.
- Remove claims about preserving a "story," improving the report, or making the document complete. State the methodological decision itself.
- Do not make the prose casual, decorative, emotional, or artificially imperfect in an attempt to sound human.

Read adjacent paragraphs as a sequence after editing. If they could be reordered without changing the argument, strengthen the logical progression or remove the paragraph that adds no distinct contribution.

## Divide work between prose and displays

Do not repeat a table or figure row by row in nearby prose. Use prose to explain the purpose, setup, important pattern, exception, or implication. Use the table or figure for parameters, categories, exact values, and comparisons. Repeat a value only when the argument depends on it.

For captions, name what the display contains and the context needed to interpret it. Do not claim that a figure proves more than its source data supports. Create or redraw technical figures only from verified code, data, or architecture. Label conceptual diagrams as conceptual and empirical plots as results.

## Structure long project documents

When the user is organizing or restructuring a project book, thesis, capstone report, or long technical report, read [project-book-structure.md](references/project-book-structure.md). Use that reference as a menu, not as a mandatory outline. The assignment, evidence, and actual work determine which sections belong.

When editing a Hebrew Word document or any right-to-left document containing English terms, code, equations, tables, or citations, read [hebrew-word-layout.md](references/hebrew-word-layout.md) before changing the file.

Before drafting, assign each claim or topic one primary section. A later section may briefly refer back to it, but should not explain it again unless it adds new evidence, interpretation, or implications.

## Edit

- Preserve the author's meaning, technical terms, facts, citations, and useful structure.
- Prefer plain words, concrete subjects, and active verbs.
- Remove repetition, filler, inflated language, empty transitions, generic openings, and generic conclusions.
- Break up sentences that are hard to parse, but allow natural variation in rhythm.
- Use one term consistently for one concept. Do not cycle through synonyms for variety.
- Keep necessary uncertainty and qualification. Do not turn a limited claim into a confident one.
- Remove stock AI phrases and abstract language that does not add information.
- Avoid forced lists, repeated summaries, decorative headings, excessive bold text, and excessive sectioning.
- Do not add examples, background, conclusions, or whole sections merely to make the document look complete.
- Keep the rewrite close to the original length when the original content is sufficient. Prefer a shorter version when cutting text improves it.

If the user sets an approval point between chapters or phases, stop there. Return the requested draft and verification notes without drafting the next phase.

## Run the unslop pass

Before returning any rewritten prose, read [unslop-checklist.md](references/unslop-checklist.md) and apply it in the language of the document. Treat the checklist as a diagnostic pass, not permission to make the writing casual or alter the author's claims. Academic and technical prose should sound human while keeping its required register.

## Verify the revision

Compare the edited text with the source before returning it. Check that no number, citation, comparison, limitation, causal claim, or degree of certainty changed accidentally. Confirm that prose does not merely duplicate an adjacent table or figure. Flag unsupported statements and source conflicts separately from the polished prose.

### Visual delivery gate for formatted documents

For Word, PDF, or another paginated document, text extraction and structural XML checks are necessary but never sufficient. Before saying that the file is ready, complete all of the following:

1. Render the exact final file into one image per page using the relevant document skill.
2. Open and visually inspect every rendered page at a readable size. Do not infer visual correctness from a successful render command, page count, extracted text, or OOXML properties.
3. Check the visible reading order, RTL/LTR transitions, headings, paragraphs, tables, equations, figures, captions, page breaks, headers, footers, contents, and automatic lists.
4. Correct every visible defect, render the corrected file again, and repeat the full-page inspection.
5. Confirm that the inspected file is byte-for-byte the same final file being delivered, or render the final saved copy once more.

Do not claim that a document was visually checked unless page images were actually opened and viewed. If rendering or image inspection is unavailable or fails, state that visual verification is incomplete and do not describe the document as ready, complete, correct, or approved. Return it only as an unverified draft when the user explicitly accepts that limitation.

Return the revised text first. Add a short note only when something needs the user's decision or could not be verified. Do not explain routine wording changes unless asked.

The edit is complete when the prose is clear and natural, no useful meaning was lost, no unsupported detail was added, no idea is repeated without a distinct purpose, and the document contains no avoidable padding.
