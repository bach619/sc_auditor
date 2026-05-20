# Protocols: SEO Optimizer Behavioral Rules

## 1. Audit Protocol

### 1.1 Full Site Audit Procedure

```
Phase 1 — Discovery:
  1. Scan all HTML files in project
  2. Identify page types (home, article, product, contact, etc.)
  3. Map URL structure
  4. Identify all <head> elements per page

Phase 2 — Content Audit:
  1. Extract and score every <title>
  2. Extract and score every <meta name="description">
  3. Count and validate heading hierarchy per page
  4. Measure word count and text-to-HTML ratio
  5. Check keyword presence in critical positions

Phase 3 — Technical Audit:
  1. Check canonical URLs
  2. Check robots meta tags
  3. Validate structured data (JSON-LD)
  4. Check Open Graph + Twitter Card presence
  5. Check viewport meta tag
  6. Check lang attribute

Phase 4 — Media Audit:
  1. Catalog all <img> elements
  2. Check alt text completeness and quality
  3. Check loading attribute strategy
  4. Check width/height or aspect-ratio
  5. Check image format recommendations

Phase 5 — Link Audit:
  1. Extract all internal links
  2. Extract all external links
  3. Check anchor text quality
  4. Check rel attributes

Phase 6 — Score & Report:
  1. Calculate weighted score
  2. Prioritize findings
  3. Output SEO Audit Scorecard
```

### 1.2 Title Scoring

```
Title Score (0-100):
  100: 50-60 chars, primary keyword near start, unique, brand at end
  80: Correct length, keyword present, unique
  60: Correct length and unique, no keyword
  40: Wrong length, no keyword, but unique
  20: Missing or duplicate
  0:  Completely missing

Deduct 10 if:
  - All uppercase
  - Keyword stuffing (>2x same keyword)
  - No brand name
```

### 1.3 Description Scoring

```
Description Score (0-100):
  100: 120-155 chars, primary keyword, CTA, unique, compelling
  80:  Correct length, keyword, unique
  60:  Keyword present, unique, wrong length
  40:  Unique but no keyword, wrong length
  20:  Duplicate or auto-generated
  0:   Missing completely
```

### 1.4 Heading Scoring

```
Heading Score (0-100):
  100: One H1, logical hierarchy (H1→H2→H3), keywords naturally in H2s
  80:  One H1, logical hierarchy
  60:  One H1, minor hierarchy issues (one skip)
  40:  Multiple H1s or major hierarchy issues
  20:  No H1, chaotic structure
  0:   No headings at all

Deduct 15 per:
  - Missing H1
  - Extra H1 (beyond one)
  - Skipped heading level
  - Empty heading tag
```

## 2. Fix Protocol

### 2.1 Critical Fix (AUTO-FIX)

```
Conditions:
  - Missing <title> → Generate from H1 + brand
  - Missing H1 → Find most prominent text, wrap in H1, or add one
  - Missing meta description → Generate from first paragraph (120-155 chars)
  - rouge meta robots with noindex → Remove or change to index, follow
  - Broken canonical → Remove if unfixable, fix URL if identifiable
  - Missing viewport → Add standard viewport meta

Procedure:
  1. Identify issue
  2. Determine fix
  3. Apply fix to file
  4. Verify fix (re-read file)
  5. Log: [AUTO-FIX] <file>:<line> — <issue> → <fix>
```

### 2.2 High Priority Fix (AUTO-FIX)

```
Conditions:
  - Missing alt text → Generate descriptive alt from context
  - Missing structured data → Generate appropriate JSON-LD
  - H1 count ≠ 1 → Fix heading levels
  - Heading skip → Adjust heading levels
  - Duplicate titles → Append unique modifier
  - Duplicate descriptions → Write unique description
  - Missing OG tags → Generate from title + description
  - Missing Twitter card → Add summary_large_image
  - HTTP in canonical → Change to HTTPS

Procedure:
  Same as critical, but logged as [HIGH-FIX]
```

### 2.3 Medium Priority (REPORT, DON'T FIX)

```
Conditions:
  - Title too short/long → Note recommendation
  - Description too short/long → Note recommendation
  - Missing keyword in H1 → Suggest rewording
  - Missing hreflang → Note for multilingual sites
  - Missing canonical → Assess if needed, if yes → fix
  - Images missing dimensions → Note with computed dimensions
  - Images not lazy-loaded → Note for below-fold images
  - Low text-to-HTML ratio → Suggest content expansion
  - Missing rel attributes on external links → Note

Behavior:
  1. Identify issue
  2. Log finding with recommendation
  3. Do NOT auto-fix — developer should review context
  4. Include in audit report under "Recommendations"
```

## 3. Structured Data Protocol

### 3.1 Schema Detection

```
Determine page type and generate appropriate schema:

1. Read page content and URL
2. Classify page type:
   - Homepage (/, /index) → WebSite + Organization
   - Contact (/contact, /hubungi) → Organization + LocalBusiness + ContactPage
   - About (/about, /tentang) → Organization + AboutPage
   - Article/Blog (/article/*, /blog/*) → Article + BreadcrumbList
   - Service (/services/*, /layanan/*) → Service + Organization
   - Product → Product + Offer
   - FAQ → FAQPage
   - Event → Event

3. Extract data from page:
   - Organization name from site title or H1
   - Logo from any logo image
   - URL from canonical or current URL
   - Description from meta description
   - Address/phone from contact section content
   - Social links from footer links

4. Validate:
   - All required fields present
   - URLs are absolute (https://)
   - Images exist and are accessible
   - Dates in ISO 8601 format
   - @context is "https://schema.org"
```

### 3.2 Schema Placement

```
JSON-LD MUST be placed:
  - In <head> (preferred) or just before </body>
  - In a single <script type="application/ld+json"> block per schema type
  - With no HTML comments inside the JSON
  - With proper JSON syntax (double quotes, no trailing commas)

Multiple schema types:
  - Combine into a @graph array, OR
  - Use separate <script> blocks (preferred for readability)
```

## 4. Performance SEO Protocol

### 4.1 LCP Optimization

```
Check hero image:
  1. Is it preloaded? → If not, add <link rel="preload" as="image" fetchpriority="high">
  2. Is it lazy-loaded? → NEVER lazy-load hero image. Change to eager.
  3. Is format optimized? → Recommend WebP/AVIF with <picture> fallback
  4. Is it above 100KB? → Flag for compression

Check render-blocking resources:
  1. CSS in <head> that blocks render → Inline critical CSS, defer rest
  2. JS in <head> without async/defer → Add defer or move to body end
  3. Font files → Add preconnect, use font-display: swap or optional
```

### 4.2 CLS Prevention

```
Check image elements:
  - Every <img> must have width AND height attributes
  - OR use CSS aspect-ratio on container
  - OR use intrinsic sizing (srcset with sizes)

Check dynamic content:
  - Ads/embeds must have reserved space (min-height or aspect-ratio)
  - Content injected above fold → Flag as CLS risk

Check web fonts:
  - Use font-display: swap or optional
  - Preload critical font files
  - Use size-adjust for fallback fonts
```

### 4.3 INP Optimization

```
Check event handlers:
  - Scroll handlers → Must be throttled/debounced or use passive listener
  - Resize handlers → Must be debounced
  - Input handlers → Check for long tasks

Check third-party scripts:
  - Load with async or defer
  - Flag heavy third-party embeds (maps, chatbots)
  - Recommend loading below fold or on user interaction

Recommendations:
  - Replace scroll event listeners with IntersectionObserver
  - Use requestAnimationFrame for animations
  - Split long synchronous tasks
```

## 5. Content Quality Protocol

### 5.1 Text-to-HTML Ratio

```
Calculate: visible_text_chars / total_html_chars

Target: > 10%

If ratio < 10%:
  - Flag: "Text-to-HTML ratio too low. Add more substantive content."
  - Minimum 300 words of quality content
  - Reduce HTML bloat (inline styles, redundant wrappers)
```

### 5.2 Keyword Placement Requirements

```
Primary keyword MUST appear in:
  1. <title> (near the beginning)
  2. First <h1>
  3. First 100 words of body text
  4. At least one <h2>
  5. Meta description

Secondary keywords SHOULD appear in:
  1. Subheadings (H2, H3)
  2. Body text (naturally, 1-2% density)
  3. Image alt text (where relevant)
  4. URL (where feasible)

Entity optimization:
  - Include related entities and synonyms
  - Use natural language patterns
  - Meet user intent (informational, transactional, navigational)
```

## 6. Mobile SEO Protocol

```
Checklist:
  [ ] <meta name="viewport"> present and correct
  [ ] Body font-size >= 16px (prevents iOS zoom on input)
  [ ] Tap targets (buttons, links) >= 48x48px
  [ ] No horizontal scroll at 375px viewport
  [ ] Content does not rely on hover states
  [ ] Forms use appropriate input types (tel, email, number)
  [ ] No fixed-width containers causing overflow
  [ ] Touch spacing between interactive elements >= 8px
  [ ] Mobile-friendly navigation (hamburger or simplified)
```

## 7. Notification Protocol

### 7.1 Audit Complete

```
Output format:

## SEO Audit Complete

**Site:** [URL or project name]
**Files Scanned:** N
**Overall Score:** XX/100 (↑YY from previous audit)

### Critical (Must Fix) — N issues
1. [CRITICAL] issue — file:line → fix applied

### High Priority — N issues
1. [HIGH] issue — file:line → fix applied

### Recommendations — N items
1. [MEDIUM] issue — recommendation
2. [LOW] issue — recommendation

### Applied Fixes
- [N] Auto-fixes applied
- [N] Issues require manual review
```

### 7.2 Silent Mode

```
SEO optimizer follows orchestrator silent mode rules:
  - Report only at audit start and complete
  - Silent during auto-fixes
  - Speak when critical blocker found
  - Full report on user request: "seo status" or "seo report"
```

## 8. Integration with BugChecker (bc)

```
bc SEO checks (overlap areas):
  - bc checks: meta tags presence, heading structure, aria labels
  - seo checks: meta tag quality, keyword optimization, schema validity

Conflict resolution:
  - If bc and seo both detect same issue → seo's fix takes priority (more nuanced)
  - If seo detects issue bc missed → seo applies fix
  - If bc flags seo's fix as issue → seo reviews, bc may be overly generic
```

## 9. Sitemap Generation Protocol

```
Procedure:
  1. Collect all indexable page URLs
  2. Determine lastmod from file modification date or git log
  3. Assign priority:
     - Homepage: 1.0
     - Main sections (about, services): 0.8
     - Sub-pages: 0.6
     - Blog/articles: 0.5
  4. Assign changefreq:
     - Homepage: weekly
     - Blog: daily (if active)
     - Static pages: monthly
  5. Output sitemap.xml
  6. Validate: well-formed XML, all URLs HTTPS, no duplicates
```

## 10. Edge Cases & Special Handling

### Single Page Applications (SPA)
```
- Use JS-rendering aware approach
- Ensure <title> and <meta> update on route change
- Add meaningful content for SSR/SSG
- Check that history.pushState URLs are crawlable
```

### Multilingual Sites
```
- Every page must have hreflang annotations
- canonical must point to current language version
- Each language version must reference ALL other language versions
- x-default required
```

### E-commerce
```
- Product schema with Offer
- AggregateRating if reviews available
- Availability (InStock, OutOfStock)
- Price with currency
- Image gallery with ItemList schema
```

### Non-Profit / Foundation Sites
```
- Organization schema with NonprofitType
- Donation schema (DonateAction) if donation page exists
- Project/Service schemas for programs
- Impact metrics in structured data where available
```
