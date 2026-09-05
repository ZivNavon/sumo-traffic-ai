# Hebrew and mixed-direction Word documents

Read this reference when creating or editing a Hebrew `.docx`, especially when Hebrew is mixed with English terms, filenames, equations, citations, or numeric expressions. Direction and alignment are separate properties. A paragraph can have right-to-left direction while still being incorrectly aligned to the left.

## Paragraphs and styles

- Set Hebrew body paragraphs to right-to-left direction and use the alignment required by the document, normally right or justified.
- Set Hebrew heading styles to right-to-left direction and right alignment. Fix the style definition so new headings inherit the correction.
- Keep English-only sections such as an English abstract or English bibliography left-to-right and left aligned.
- Apply the same rules to headers, footers, footnotes, captions, text boxes, and table cells.

## Mixed Hebrew and English

- Keep the paragraph direction Hebrew, but mark English terms, acronyms, filenames, paths, formulas, and code fragments as left-to-right runs.
- Keep punctuation with the phrase it belongs to. Inspect colons, parentheses, hyphens, slashes, equation numbers, and caption numbers after rendering.
- Prefer a stable visible form such as `איור 5:` or `משוואה (1):`. Do not accept a result that renders as `איור: 5` or reverses an English identifier.
- Do not repair mixed-direction text by inserting visible punctuation or spaces until it appears correct in the editor. Set the underlying run direction and then render the document.

## Tables and equations

- Set Hebrew tables to right-to-left table order. Put the main descriptive field in the rightmost column unless the required template specifies otherwise.
- Set the direction and alignment of each cell independently. English-only cells may remain left-to-right even inside a Hebrew table.
- Use native Word equation objects for displayed mathematics. Keep mathematical content left-to-right and verify the placement of equation numbers in the rendered page.

## Contents and numbered lists

- Build the table of contents from Word heading styles. Do not type page numbers manually.
- Build lists of figures, tables, and equations from captions and Word fields such as Caption and SEQ when the format supports them.
- Update all fields after pagination changes. Check that every displayed page number points to the actual item.
- A partial draft may use temporary lists only when the user agrees. Label them as temporary rather than reporting them as updated automatic fields.

## Visual verification

Render the complete document after editing. Inspect every page at readable size, with extra attention to:

- the table of contents and lists;
- mixed Hebrew-English headings and paragraphs;
- captions and cross-references;
- tables, formulas, filenames, and citations;
- the first and last lines of pages where reflow can expose direction errors.

Structural checks are useful but do not replace visual inspection. Completion requires both correct document properties and a readable rendered result.

The agent must actually open the rendered page images and look at them. A renderer exit code, generated PDF, extracted text, accessibility report, field count, or RTL property count does not establish that the document is visually correct. If even one page has not been viewed, the document has not passed visual verification.

After any correction that can change pagination or layout, render again and re-inspect all affected pages; for broad style, direction, field, or equation changes, re-inspect every page. If rendering cannot be completed, label the output as an unverified draft and never say that it is ready.
