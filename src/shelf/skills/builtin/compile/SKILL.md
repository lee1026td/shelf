---
name: compile
description: Synthesize a cited brief/landscape on a topic from the library's sources.
toolset: compile
---

# Goal
Write a well-organized, **cited** document on the user's topic, grounded in the
library's existing sources and items. You compile from what is already known — you do
NOT add new sources here.

# How to work
1. `library_search` to gather the items and known sources relevant to the topic.
2. Use `fetch_url` on a few of the most relevant source URLs to pull enough detail to
   write accurately — but keep it to a handful; you have a limited step budget.
3. When you have enough material, finish: the final action's `answer` is the FULL
   document in Markdown.

# The document
- Start with a short `## Overview`, then organize the body into clear sections with
  `##` headings appropriate to the requested kind (brief, landscape, FAQ, timeline).
- **Every factual claim must cite a source you actually read**, inline by URL, like
  `(https://example.com)`. Do not invent sources or facts. If the library lacks
  material for a point, say so rather than guessing.
- End with a `## Sources` list of the URLs you used.

# Rules
- Ground strictly in the library/sources you read; this is not free-form generation.
- Be concise and concrete; prefer specifics over generalities.
