# Verbatim User Evidence Bank: Visual Memory Retrieval Breakdowns

---

> [!IMPORTANT]
> **Veracity & Privacy Certification:**
> 1. **100% Verbatim:** Every quote below is programmatically verified as an exact word-for-word substring from the original public discussion.
> 2. **Zero PII:** All personal identifiers (names, handles, emails, device IDs, GPS coordinates) have been strictly stripped (`[USER]`, `[PERSON]`, `[FAMILY_MEMBER]`, `[DEVICE]`).
> 3. **Uninvented Reality:** No paraphrasing, LLM hallucinations, or synthetic wording have been introduced.

---

## 1. Evidence Distribution Summary

- **Total Verified Quotes:** 16
- **Distinct Failure Archetypes:** 5
- **Primary Problem Spaces:** 2

| Failure Mode | Quote Count | Primary Photo Categories | Mean Frustration (1-5) |
| :--- | :--- | :--- | :--- |
| `ocr_failure` | **8** | document, receipt, screenshot | 3.62 / 5.0 |
| `semantic_drift` | **4** | candid portrait | 3.0 / 5.0 |
| `chronological_overload` | **2** | candid portrait, vacation photo | 3.5 / 5.0 |
| `other` | **1** | other | 4.0 / 5.0 |
| `zero_results` | **1** | screenshot | 3.0 / 5.0 |

---

## 2. Categorized Verbatim Evidence

### Problem Archetype: `ocr_failure`

**Cluster Association:** `cluster_02` — *Document OCR & Numerical Receipt Indexing Failure*
> Users recall text-heavy media (receipts, stickers, bills, invoices) by prices, merchant names, or partial words. Search fails due to unindexed small printed/handwritten text or currency symbols.

#### Evidence Item 1 (Screenshot)
> "typing 'pistachio lemon recipe' brings up absolutely nothing"

- **Photo Category:** `screenshot`
- **Remembered Cues:** recipe had pistachio crust (object_scene), recipe had lemon curd (object_scene)
- **Forgotten Details:** exact filename, date saved, source website or app
- **Attempted Search Queries:** `pistachio lemon recipe`
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_9f48a1b7258d`

#### Evidence Item 2 (Receipt)
> "Searched 'Costco $320' and nothing came up."

- **Photo Category:** `receipt`
- **Remembered Cues:** Costco $320 (document_ocr)
- **Forgotten Details:** exact date, filename
- **Attempted Search Queries:** `Costco $320`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_fb7a92d06e4f`

#### Evidence Item 3 (Screenshot)
> "searching 'passionfruit chocolate recipe' brings up 0 results because OCR failed on cursive font."

- **Photo Category:** `screenshot`
- **Remembered Cues:** passionfruit and white chocolate (object_scene)
- **Forgotten Details:** exact recipe title, source website or app, date of screenshot
- **Attempted Search Queries:** `passionfruit chocolate recipe`
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_afb132fa01d0`

#### Evidence Item 4 (Receipt)
> "Thumbnails in search results are way too small to evaluate receipts or document screenshots."

- **Photo Category:** `receipt`
- **Remembered Cues:** serial number (document_ocr)
- **Forgotten Details:** exact date, specific merchant, filename
- **Attempted Search Queries:** `receipt`
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_b93482025858`

#### Evidence Item 5 (Receipt)
> "Searching '$1249' or 'Best Buy' returns zero items even though I know the picture is in my archive."

- **Photo Category:** `receipt`
- **Remembered Cues:** early 2022 (temporal), laptop (object_scene), $1,249.99 (document_ocr), Best Buy (object_scene)
- **Forgotten Details:** exact date, filename, specific store location
- **Attempted Search Queries:** `$1249`, `Best Buy`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_4b0754f85686`

#### Evidence Item 6 (Receipt)
> "I searched for 'Amoxicillin' and 'prescription' which is printed clearly on the receipt slip, but Google Photos returns zero results."

- **Photo Category:** `receipt`
- **Remembered Cues:** Amoxicillin (document_ocr), prescription (document_ocr)
- **Forgotten Details:** exact date, filename
- **Attempted Search Queries:** `Amoxicillin`, `prescription`
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_11ce37c83358`

#### Evidence Item 7 (Receipt)
> "Search seems to completely ignore dollar signs and price numbers on paper receipts."

- **Photo Category:** `receipt`
- **Remembered Cues:** total was $499 (document_ocr), Home Depot (object_scene)
- **Forgotten Details:** exact date, specific item purchased, store location
- **Attempted Search Queries:** `$499`, `Home Depot receipt`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_f9ec2ba80316`

#### Evidence Item 8 (Document)
> "Google Photos OCR didn't index the plate numbers at all"

- **Photo Category:** `document`
- **Remembered Cues:** license plate number (document_ocr)
- **Forgotten Details:** exact date, filename, specific visual context of the photo
- **Attempted Search Queries:** `license plate number`
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_408ee32a7087`

---

### Problem Archetype: `semantic_drift`

**Cluster Association:** `cluster_01` — *Visual Attribute & Color-Scene Semantic Mismatch*
> Users recall salient visual cues (clothing colors, background structures, or negated attributes like 'not smiling'). Search produces semantic drift (e.g. matching 'yellow jacket' to wasps or 'red barn' to red cars).

#### Evidence Item 1 (Candid Portrait)
> "Searching 'red barn' shows red cars and barns from vacations in 2023."

- **Photo Category:** `candid portrait`
- **Remembered Cues:** red barn in Vermont (object_scene), maybe 2018 or 2019 (temporal), face is turned sideways (visual_color)
- **Forgotten Details:** exact year, specific filename or location in album
- **Attempted Search Queries:** `red barn`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_0e16844b37f7`

#### Evidence Item 2 (Candid Portrait)
> "It literally can't connect the color red to clothing."

- **Photo Category:** `candid portrait`
- **Remembered Cues:** red sweater (visual_color), two years ago (temporal), Christmas (lifeevent_anchor)
- **Forgotten Details:** exact date, specific location, other people in the photo
- **Attempted Search Queries:** `red sweater`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_b1df117f35d4`

#### Evidence Item 3 (Candid Portrait)
> "Searching 'blue dinosaur costume' returns photos of green toy dinosaurs and random blue shirts, but not her costume."

- **Photo Category:** `candid portrait`
- **Remembered Cues:** 2022 (temporal), blue (visual_color), dinosaur Halloween costume (object_scene), wearing her blue dinosaur Halloween costume (activity)
- **Forgotten Details:** exact date, filename, specific location
- **Attempted Search Queries:** `blue dinosaur costume`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_3f9e9e019481`

#### Evidence Item 4 (Candid Portrait)
> "The search engine completely ignores adjectives."

- **Photo Category:** `candid portrait`
- **Remembered Cues:** wearing a green jacket (visual_color)
- **Forgotten Details:** exact location, date, identity of the person
- **Attempted Search Queries:** `green jacket`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_cb895af857c6`

---

### Problem Archetype: `chronological_overload`

#### Evidence Item 1 (Vacation Photo)
> "If you guess 2018 and it was 2019, you get nothing."

- **Photo Category:** `vacation photo`
- **Remembered Cues:** sometime before COVID (temporal), camping trip (activity)
- **Forgotten Details:** exact year, exact month
- **Attempted Search Queries:** `2018`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_512e3d0865cd`

#### Evidence Item 2 (Candid Portrait)
> "I tried 'black hoodie' and got 500 pictures, had to scroll forever."

- **Photo Category:** `candid portrait`
- **Remembered Cues:** wearing a black hoodie (visual_color), NOT someone was NOT smiling (activity)
- **Forgotten Details:** exact date, location, other people in the photo, background details
- **Attempted Search Queries:** `black hoodie`
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_d05d650ccc01`

---

### Problem Archetype: `other`

#### Evidence Item 1 (Other)
> "Just stop. I’ll come looking for what I want and need when I’m ready."

- **Photo Category:** `other`
- **Remembered Cues:** other (object_scene)
- **Forgotten Details:** None specified
- **Attempted Search Queries:** None recorded
- **User Friction Level:** 4 / 5.0
- **Record Traceability ID:** `rec_2e681caa7d45`

---

### Problem Archetype: `zero_results`

#### Evidence Item 1 (Screenshot)
> "If my query returns 0 results, give me filter chips like 'Search in Screenshots' or 'Search by Year'. Instead it just shows a blank screen and I have to start over from scratch."

- **Photo Category:** `screenshot`
- **Remembered Cues:** The photo is likely a screenshot, inferred from the user's suggestion to use a 'Search in Screenshots' filter (other)
- **Forgotten Details:** exact content of the photo, specific year or date, filename
- **Attempted Search Queries:** `unspecified query that returned 0 results`
- **User Friction Level:** 3 / 5.0
- **Record Traceability ID:** `rec_cd527bed39ac`

---
