"""
PhilVerify — Text Preprocessor
Handles cleaning, tokenizing, and normalizing Filipino/English/Taglish text.
"""
import re
import string
import unicodedata
from dataclasses import dataclass, field

# ── Filipino + English stopwords ──────────────────────────────────────────────
TAGALOG_STOPWORDS = {
    "ang", "ng", "na", "sa", "at", "ay", "mga", "ni", "nang", "si",
    "ko", "mo", "siya", "kami", "kayo", "sila", "ito", "iyon", "iyan",
    "dito", "doon", "diyan", "nito", "noon", "niyan", "rin", "din", "pa",
    "lang", "lamang", "nga", "naman", "kaya", "pero", "dahil", "kung",
    "kapag", "habang", "bilang", "upang", "para", "mula", "hanggang",
    "ayon", "sinabi", "raw", "daw", "ba", "po", "ho", "oh", "oo",
    "hindi", "wala", "may", "mayroon", "talaga", "pala", "sana",
}

ENGLISH_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "not", "no", "nor", "so", "yet", "both", "either", "neither",
    "this", "that", "these", "those", "it", "its", "i", "me", "my",
    "we", "our", "you", "your", "they", "their", "he", "his", "she", "her",
}

ALL_STOPWORDS = TAGALOG_STOPWORDS | ENGLISH_STOPWORDS

# ── Patterns ──────────────────────────────────────────────────────────────────
_URL_PATTERN = re.compile(
    r"http[s]?://(?:[a-zA-Z]|[0-9]|[$\-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_MENTION_PATTERN = re.compile(r"@\w+")
_HASHTAG_PATTERN = re.compile(r"#\w+")
_REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{2,}")  # "graaabe" → "grabe"
_EXCESSIVE_PUNCT_PATTERN = re.compile(r"([!?.]){2,}")
_WHITESPACE_PATTERN = re.compile(r"\s+")

# Emoji removal via unicode category
def _remove_emojis(text: str) -> str:
    return "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith("So")  # Symbol, Other
        and unicodedata.category(ch) not in ("Mn",)       # Modifier letters
    )


@dataclass
class PreprocessResult:
    original: str
    cleaned: str
    normalized: str
    tokens: list[str] = field(default_factory=list)
    filtered_tokens: list[str] = field(default_factory=list)
    char_count: int = 0
    word_count: int = 0


class TextPreprocessor:
    """
    Multi-step text cleaner for Tagalog / English / Taglish content.

    Pipeline:
        1. strip_html       — remove HTML tags
        2. strip_urls       — remove hyperlinks
        3. strip_mentions   — remove @user
        4. strip_hashtags   — remove #tag text (keep token)
        5. strip_emojis     — remove Unicode emoji
        6. lowercase        — normalize case
        7. normalize_chars  — collapse repeated chars, excessive !??
        8. strip_punct      — remove punctuation except apostrophe
        9. tokenize         — split on whitespace
       10. remove_stopwords — drop EN + TL stopwords
    """

    def clean(self, text: str) -> str:
        """Steps 1-6: structural cleaning."""
        text = _HTML_TAG_PATTERN.sub(" ", text)
        text = _URL_PATTERN.sub(" ", text)
        text = _MENTION_PATTERN.sub(" ", text)
        text = _HASHTAG_PATTERN.sub(lambda m: m.group(0)[1:], text)  # Keep word, drop #
        text = _remove_emojis(text)
        text = text.lower()
        return _WHITESPACE_PATTERN.sub(" ", text).strip()

    def normalize(self, text: str) -> str:
        """Steps 7-8: character-level normalization."""
        text = _REPEATED_CHAR_PATTERN.sub(r"\1\1", text)   # "graaabe" → "graabe"
        text = _EXCESSIVE_PUNCT_PATTERN.sub(r"\1", text)   # "!!!" → "!"
        # Keep apostrophes (di, 'di, hindi), remove other punct
        text = "".join(
            ch if ch not in string.punctuation or ch == "'" else " "
            for ch in text
        )
        return _WHITESPACE_PATTERN.sub(" ", text).strip()

    def tokenize(self, text: str) -> list[str]:
        """Step 9: whitespace tokenization."""
        return [t for t in text.split() if len(t) > 1]

    def remove_stopwords(self, tokens: list[str]) -> list[str]:
        """Step 10: remove EN + TL stopwords."""
        return [t for t in tokens if t not in ALL_STOPWORDS]

    def preprocess(self, text: str) -> PreprocessResult:
        """Run the full pipeline and return a structured result."""
        cleaned = self.clean(text)
        normalized = self.normalize(cleaned)
        tokens = self.tokenize(normalized)
        filtered = self.remove_stopwords(tokens)
        return PreprocessResult(
            original=text,
            cleaned=cleaned,
            normalized=normalized,
            tokens=tokens,
            filtered_tokens=filtered,
            char_count=len(normalized),
            word_count=len(tokens),
        )
