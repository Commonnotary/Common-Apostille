# GEO Gap Analysis & Action Plan: Common Notary Apostille

Prepared by: **Manus AI**  
Date: May 27, 2026  

---

## 1. Executive Summary

This document outlines the Generative Engine Optimization (GEO) gap analysis and implementation roadmap for **Common Notary Apostille (CNA)**. Based on the 2026 search engine and AI landscape [1], where up to 25% of traditional search queries are migrating to generative AI systems (such as ChatGPT, Perplexity, Google AI Overviews, Claude, and Gemini) [1], having a robust, machine-readable, and highly structured digital presence is critical. 

The audit of the `Common-Apostille` repository reveals a single-page website (`index.html`) with excellent on-page conversion elements but zero structural presence for secondary landing pages, schema markup, or programmatic SEO. While high-quality content strategies and copywriting assets exist as markdown files inside the `seo_deliverables/` folder, they have not yet been deployed to the live website. This gap prevents AI crawlers from indexing, referencing, and citing CNA when attorneys search for premium notary and apostille coordination services in the DMV area.

---

## 2. GEO Gap Analysis

| Optimization Category | Current State | GEO Best Practice (2026) | Gap Severity | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Site Architecture & Multi-Page Indexing** | Single-page (`index.html`, `china.html`). No dedicated service or location URLs. | Logical, multi-page structure with clean slugs (`/service/...`, `/locations/...`) [2]. | **Critical** | Build out separate pages for core services and high-priority locations using the pre-written content. |
| **Schema Markup (JSON-LD)** | None present in `index.html` or `china.html`. | Explicit `LegalService`, `FAQPage`, and `BreadcrumbList` schema in page headers [1] [2]. | **High** | Inject JSON-LD schema into the homepage and newly created landing pages. |
| **Answer-Capsule Content Structure** | Standard promotional text on the homepage. No direct Q&A blocks. | Clear, factual H2/H3 headings followed immediately by a 40-60 word "Answer Capsule" [1]. | **High** | Structure newly deployed service and FAQ pages using the Answer Capsule methodology. |
| **AI Crawler Accessibility (`llms.txt`)** | `llms.txt` exists but links to non-existent URLs (e.g., `/service/...`). | `llms.txt` should serve as a valid map pointing to actual, live, crawlable HTML pages [1] [2]. | **Medium** | Update `llms.txt` to point to the newly created live HTML pages. |
| **Target Audience Alignment & Messaging** | Homepage lists pricing starting at $297 for Apostille. | Focus on B2B legal audience (estate planning, elder law, probate) with accurate pricing ($649 for digital proceedings) [3] [4]. | **Medium** | Ensure all content highlights the specialized legal niche and complies with marketing restrictions [5]. |

---

## 3. Recommended Website Architecture

To satisfy both traditional search crawlers and AI search retrievers (RAG systems) [2], we will expand the single-page site into a highly organized multi-page directory. The routing will follow the pre-existing SEO architecture plan:

1. **Homepage (`/`)**: Main entry point highlighting the three core service pillars (Apostille, Estate Notarization, Digital Depositions).
2. **Specialized Service Pages**:
   * `/service/washington-dc-estate-planning-notary-attorneys` (Attorney-focused landing page)
   * `/service/apostille-authentication` (Core apostille coordination page)
   * `/service/digital-deposition-services` (Court reporting & digital proceedings page)
3. **FAQ Directory (`/faq`)**: Dedicated Q&A hub structured specifically for AI answer engines.
4. **Global Expansion / China Section (`/china`)**: Dedicated portal for international apostille and translation coordination, listed directly on the homepage.

---

## 4. References

* [1] Search Engine Land. (2026). *Mastering Generative Engine Optimization in 2026: Full Guide*. [https://searchengineland.com/mastering-generative-engine-optimization-in-2026-full-guide-469142](https://searchengineland.com/mastering-generative-engine-optimization-in-2026-full-guide-469142)
* [2] Google Search Central. (2026). *Optimizing your website for generative AI features on Google Search*. [https://developers.google.com/search/docs/fundamentals/ai-optimization-guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
* [3] Common Notary Apostille. (2026). *Lead Generation and Pricing Guidelines*. Internal Knowledge Base.
* [4] Common Notary Apostille. (2026). *Target Audience and Legal Specialties Expansion*. Internal Knowledge Base.
* [5] Common Notary Apostille. (2026). *Marketing Content Restrictions*. Internal Knowledge Base.
