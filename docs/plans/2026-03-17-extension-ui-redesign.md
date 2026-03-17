# PhilVerify Extension — UI Redesign
**Date:** 2026-03-17

## Goals
1. Surface new backend fields (`model_tier`, `claim_method`, `stance_reason`) without cluttering the UI
2. Make the verdict scannable in under 2 seconds across all surfaces
3. Visual consistency between side panel, inline modal, and history tab

## Information Hierarchy

Four tiers, consistent across all surfaces:

| Tier | Content | Style |
|------|---------|-------|
| 1 | Verdict label | Large, bold, verdict color |
| 2 | Credibility score | Medium weight, verdict color, slightly smaller |
| 3 | Signals + top source | Normal weight, neutral text |
| 4 | model_tier, claim_method | 10px monospace, muted #6b7280 |

**Visual anchor:** 3px left border in verdict color on every result card.

**Theme:** dark newsroom — `#0d0d0d` bg, `#1a1a1a` card surface, `#262626` borders.

---

## Side Panel Result Card (`popup.js renderResult`)

**Top block**
- 3px left border (verdict color)
- Verdict label: 20px bold, verdict color
- Score: same line, right-aligned
- 1px colored hairline separator below

**Middle block**
- Triggered features: small inline chips (dark bg, verdict-colored border, 10px)
- Top source: distinct link block with `#1a1a1a` bg, `#262626` border, site name + truncated title + ↗

**Footer block**
- `border-top: 1px solid #262626`, 8px top padding
- `MODEL  ensemble    CLAIM VIA  sentence_scoring`
- 10px monospace, labels `#4b5563`, values `#6b7280`

**Bottom**
- "Open Full Dashboard ↗" as full-width footer button with `border-top: 1px solid #262626`

---

## Inline Modal (content.js / content.css)

Injected as full-width block below post. Fixed width ~320px. Same left-border spine pattern.

```
┌───────────────────────────────────────┐
▌ LIKELY FAKE              84% credibility
▌ ─────────────────────────────────────
▌ Signals: clickbait_title, no_byline
▌ Top Source: Rappler — "Claim is false…" ↗
▌ ─────────────────────────────────────
▌ model: ensemble  ·  via: sentence_scoring
└───────────────────────────────────────┘
```

- Line 1: Verdict (bold, verdict color) + score right-aligned
- Line 2: Hairline separator (verdict color, 30% opacity)
- Line 3: Signals (up to 3, comma-separated)
- Line 4: Top source title truncated at 45 chars + ↗
- Line 5: Hairline separator
- Line 6: model_tier · claim_method — 10px monospace, muted

- `×` dismiss button top-right
- "Verify this post" button replaced in-place by result block after verification

---

## History Tab

Entry layout (~60px tall per item):

```
┌─────────────────────────────────────────┐
▌ ● LIKELY FAKE  84%    ensemble          ▌
▌ "Marcos signs new law allowing…"        ▌
▌ 2h ago                                  ▌
└─────────────────────────────────────────┘
```

- Row 1: Colored dot + verdict chip + score + model_tier (muted monospace, pushed right)
- Row 2: Text preview (#9ca3af, 12px)
- Row 3: Timestamp (#6b7280, 10px)
- Left border: 2px solid verdict color
- Hover: `background: #1a1a1a`

Empty state: centered 32px shield SVG outline (muted) + "No verifications yet." below it.

---

## Files to Modify

| File | Changes |
|------|---------|
| `extension/popup.js` | Rewrite `renderResult()`, update `renderHistory()` |
| `extension/popup.css` | Add `.result-spine`, `.result-footer-meta`, `.result-chip`, update `.history-item` |
| `extension/content.js` | Update modal HTML template |
| `extension/content.css` | Update `.pv-badge` / modal styles, add spine + footer-meta |
