# PhilVerify Defense Outline

## Project Positioning

**Title:** PhilVerify: NLP-Assisted Fake News and Claim Credibility Detection for Philippine Social Media

PhilVerify is an NLP project because it analyzes natural language from pasted posts, URLs, and screenshot OCR. The system performs text preprocessing, language detection, entity extraction, sentiment/clickbait analysis, claim extraction, text classification, and evidence matching.

The system predicts credibility. It does not claim to prove absolute truth.

## Dataset Story

| Source | Purpose | How to explain it |
|--------|---------|-------------------|
| `jcblaise/fake_news_filipino` | Main training dataset | Filipino benchmark dataset for real/fake news classification |
| `philverify_handcrafted` | Training supplement | Adds Tagalog, Taglish, and `Unverified` examples |
| Rappler / VERA Files samples | Training supplement and evidence examples | Fact-check verdicts are mapped into the 3-label system |
| `facebook_style_claims.csv` | Evaluation only | Tests short Facebook-style claims separately from training |
| Trusted PH news domains | Evidence layer | Used to support or refute claims, not as automatic truth labels |

Main defense line:

> We use public Filipino fake-news data for training, then evaluate separately on Facebook-style posts because social media language is shorter, noisier, and more informal than news articles.

## System Flow

1. The user submits text, a URL, or a screenshot.
2. The app extracts text through direct input, URL scraping, or OCR.
3. The NLP pipeline cleans the text, detects language, extracts entities, and identifies the main claim.
4. The classifier predicts `Credible`, `Unverified`, or `Likely Fake`.
5. The evidence layer searches trusted Philippine news and fact-check sources.
6. The final score combines classifier output, evidence signals, and source/domain credibility.

## Evaluation Story

Report two separate results:

- Main validation split: shows model behavior on the processed training dataset.
- Facebook-style evaluation set: shows behavior on the target demo setting.

Use these metrics:

- Accuracy
- Precision
- Recall
- F1 score
- Confusion matrix

Important note:

> We pay special attention to `Unverified` because it represents uncertainty and has fewer examples than the binary real/fake classes.

## Scope

Included:

- Text verification
- URL/article verification
- Screenshot OCR verification
- Browser extension as a demo/application layer
- Trusted Philippine evidence retrieval

Not included in final website scope:

- Video/audio verification
- Guaranteed truth rulings
- Private Facebook scraping
- Professional fact-check replacement

## Limitations

- Facebook posts can lack context.
- OCR can misread low-quality screenshots.
- Satire and sarcasm are difficult.
- Source matching can fail if the claim is too vague.
- `Unverified` is inherently harder than real/fake classification.

## Suggested Closing

PhilVerify is best understood as a research and educational tool that helps users slow down before sharing. It uses NLP and evidence retrieval to produce a credibility signal, but the final responsibility remains with the user to check reliable sources.
