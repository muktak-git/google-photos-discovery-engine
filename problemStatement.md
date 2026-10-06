# Project Context & Problem Statement: AI-Powered Photo Retrieval Discovery Engine

---

## 1. Executive Summary & Core Objective

The primary objective of this project is to **increase the percentage of users who successfully retrieve a photo they remember but cannot precisely describe** when initiating a search.

> [!IMPORTANT]
> **Scope Distinction:** The challenge is **not** to improve photo search in general (e.g., query speed, general UI navigation, or broad metadata indexing). The explicit focus is understanding the cognitive gap in human visual memory—how people recall past visual information, where existing retrieval experiences fail, and identifying high-impact opportunity areas to bridge this gap.

To solve this, we are building an **AI-powered discovery engine** capable of analyzing public user feedback, discussions, and support queries **at scale**. The engine translates unstructured user voice into structured, evidence-backed retrieval problems and actionable opportunity areas for product and engineering teams.

---

## 2. End-to-End Flow (Definition of "Done")

The discovery engine operates across five sequential stages:

```
+-----------------------------------------------------------------------------------+
| 1. Ingest Public Conversations                                                    |
|    Play Store, App Store, Support Forums, Reddit, YouTube, Social Media          |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 2. Relevancy & Intent Filtering                                                   |
|    Isolate queries regarding partially remembered photos from generic app noise   |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 3. Structured Signal Extraction                                                   |
|    Photo type, remembered details, forgotten details, search phrasing, failure pts|
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 4. Problem Clustering & Comparative Evidence Analysis                            |
|    Aggregate into distinct failure modes; evaluate frequency and severity         |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
| 5. Opportunity Synthesis & Recommendation                                         |
|    Rank opportunity spaces backed by verbatim, privacy-stripped user quotes       |
+-----------------------------------------------------------------------------------+
```

1. **Ingest Public Conversations:** Ingest user feedback from diverse public channels (Google Play Store, Apple App Store, Google Photos community/support threads, Reddit, forums, YouTube comments, social media) capturing source, timestamp, and raw text.
2. **Relevancy Filtering:** Filter raw data down to interactions specifically describing retrieval attempts where memory was vague, partial, or imprecise.
3. **Structured Signal Extraction:** Extract cognitive and behavioral signals:
   - *Photo Category / Type* (e.g., screenshot, document, candid family photo, receipt, vacation landmark).
   - *Remembered Details* (e.g., approximate year, color of a shirt, background object, ambient setting).
   - *Forgotten Details* (e.g., exact date/month, location tag, filename, person's name).
   - *Search Phrasing / Strategy* (e.g., natural language queries, keyword combinations, visual browsing).
   - *Failure Mechanism* (e.g., semantic mismatch, OCR failure, chronological overload, zero results).
4. **Clustering & Problem Mapping:** Group extracted signals into distinct, recurring retrieval problem archetypes and measure their incidence and user friction.
5. **Opportunity Synthesis:** Rank potential opportunity areas and propose the single most impactful retrieval improvement, thoroughly supported by verbatim user evidence.

---

## 3. Key Discovery Questions

The discovery engine must extract and analyze data to answer critical questions regarding human recall:

- **Photo Typology:** What specific categories of old photos do users struggle most to retrieve?
- **Salient Recall Signals:** What sensory, temporal, emotional, or contextual cues do users actually retain over time?
- **Cognitive Blind Spots:** What key metadata or descriptive attributes do users consistently forget?
- **Query Formulation:** How do users express incomplete memories into search inputs when traditional keyword or face/place filters fall short?
- **Friction Points:** Where does the transition between mental model and search engine syntax collapse?

---

## 4. Key Deliverables & Artifacts

| Deliverable | Description |
| :--- | :--- |
| **Retrieval Problem Map** | A comparative taxonomy of distinct retrieval failure modes, mapped across frequency of occurrence and severity of user impact. |
| **Verbatim User Evidence Bank** | Authentic, unaltered quotes extracted directly from public discussions illustrating each problem pattern (with PII strictly stripped). |
| **Opportunity Analysis & Roadmap** | Ranked opportunity spaces addressing identified bottlenecks, highlighting one primary, evidence-backed recommendation for immediate product intervention. |

---

## 5. Stakeholder Value Matrix

| Audience | Strategic Value & Usage |
| :--- | :--- |
| **Product & Growth** | Prioritize feature investments and roadmap items with the highest probability of improving search task completion rates. |
| **Research & Design (UX/UR)** | Ground search UX patterns in real-world human recall habits rather than assuming users remember concrete dates or locations. |
| **Engineering & Machine Learning** | Design embedding models, multi-modal search indices, and semantic parsers tailored to the specific memory cues users employ. |
| **Leadership** | Gain an evidence-based, executive-level synthesis of search bottlenecks without wading through thousands of noisy support tickets. |

---

## 6. Functional Architecture & Components to Build

- **Multi-Source Ingestion Pipeline:** Automated pipelines to collect public discussions with metadata preservation (`source`, `text`, `timestamp`, `url/thread_id`).
- **Heuristic & LLM Relevance Filter:** Binary and multi-class classification to separate general bug reports/complaints from genuine photo recall and retrieval struggles.
- **Cognitive Signal Extractor:** Structured schema extraction parsing user narratives into machine-readable JSON entities (photo type, recalled attributes, missing attributes, search terms, failure reasons).
- **Semantic Clustering Engine:** Unsupervised/semi-supervised clustering grouping similar failure modes into macro problem spaces.
- **Opportunity Evaluator:** Algorithmic ranking framework combining volume, sentiment frustration score, and feasibility to output concrete recommendations.

---

## 7. Key Constraints & Guardrails

> [!CAUTION]
> Compliance with the following constraints is mandatory throughout the project:

- **Public Data Only:** Utilize strictly publicly accessible data sources. No private data, no login-walled accounts, and no Terms-of-Service-violating scraping methods.
- **Laser-Focused Scope:** Restrict the problem boundary strictly to **imprecise memory retrieval**. Discard generic search performance issues, UI redesign debates, or unrelated cloud sync bugs.
- **Depth Over Surface Summaries:** Avoid basic sentiment analysis (e.g., positive vs. negative) or simple word clouds. Deliver granular cognitive signal extraction, failure mode mapping, and comparative trade-off analyses.
- **Verbatim Evidence Integrity:** Every finding, cluster, and hypothesis must be anchored by real, unaltered user quotes. Never fabricate, hallucinate, or rewrite quotes.
- **Privacy & Anonymization (Zero PII):** All usernames, handles, email addresses, phone numbers, location specifics, device serials, and identifiers must be stripped prior to storage and presentation.
