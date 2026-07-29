CRITICAL REQUIREMENT: You are given EXACTLY {{chunk_size}} news items numbered 1 to {{chunk_size}}.
You MUST return the 'results' array with EXACTLY {{chunk_size}} elements.
Each element MUST correspond 1-to-1 to the input item at the exact same index order. Do NOT skip, merge, or reorder any items.
Evaluate macro impact score (1-10) and asset impact score (1-10) for each news item below.
IMPORTANT requirement: You MUST provide 'thai_title' (accurate headline translated into THAI language) and 'thai_summary' (CONCISE analytical summary written in THAI language maximum 2-3 sentences for Thai investors. Do NOT write paragraphs).
Rubric:
- Score >= 7 (HIGH IMPACT): Systemic macro shift, central bank rate decision, critical policy change, inflation surprise, systemic shock, or market-moving earnings/catalyst (e.g. NVDA, PTT).
- Score < 7 (ROUTINE IMPACT): Minor commentary, routine update, or localized news without broad market impact.
News items to evaluate:
{{news_items}}
