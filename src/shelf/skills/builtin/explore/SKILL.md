---
name: explore
description: Discover and propose sources for a research topic, then write a cited brief.
toolset: discovery
---

# Goal
Propose a SMALL SET of distinct, high-quality sources for the user's topic (aim for
3-6), then write a short cited brief. You have a limited number of tool steps, and
EVERY tool call (searches and page reads included) uses one — so spend them on
proposing, not on reading every page.

# How to work (propose-first)
1. `library_search` once to see what the user already has.
2. If web search is available, `web_search` for the topic. Try 1-2 query VARIATIONS if
   the first is weak — different keywords, and both English and the user's language —
   since one phrasing can miss good sources. If it reports that remote search is
   disabled, do NOT retry it — work from the library and finish.
3. **Propose directly from the search results.** For each result that clearly fits the
   topic, call `propose_source` straight away using the title + URL from the search
   list. You do NOT need to fetch a page before proposing it. Include a `relevance`
   estimate (0.0-1.0) when you can.
4. Use `fetch_url` ONLY to settle a genuine doubt about one or two ambiguous results —
   not as a routine step. Reading three pages can exhaust your whole budget.
5. Keep going until you have proposed 3-6 distinct sources, then finish. Do not emit
   the final action while you still have budget and fewer than 3 good sources proposed
   (unless search genuinely returned nothing).

# Finishing
Reply with the final action whose `answer` is a 3-6 sentence brief on the topic. Every
claim must cite a source you actually found, by URL, like `(https://example.com)`. If
you could not find good sources, say so plainly rather than inventing any.

# Rules
- Prefer primary/original sources over aggregators; favor distinct sites over many
  pages from one site. Never propose the same URL twice.
- One `propose_source` call per source; give a clear `name`, a `role` (blog, docs,
  news, paper, forum), and a one-line `reason`.
- You are only *proposing* — sources go to a review queue, nothing is watched or added.
