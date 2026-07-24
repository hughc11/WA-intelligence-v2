"""
WA Intelligence
Daily briefing generator
Version 2.0 — intelligence scoring

This script:
1. Searches public Google News RSS feeds.
2. Collects genuinely recent West Africa stories.
3. Rejects weakly relevant and unsuitable stories.
4. Scores publisher quality and political-risk relevance.
5. Keeps the strongest report when several outlets cover one event.
6. Produces a balanced briefing.json for the website.
7. Scores political, economic, security and regional impact.
8. Adds confidence and priority ratings for each story.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


# ==========================================================
# PROJECT SETTINGS
# ==========================================================

PROJECT_FOLDER = Path(__file__).resolve().parent
OUTPUT_FILE = PROJECT_FOLDER / "briefing.json"

NUMBER_OF_STORIES = 10
REQUEST_TIMEOUT_SECONDS = 20
MAX_STORY_AGE_HOURS = 36

MIN_RELEVANCE_SCORE = 4
MIN_FINAL_SCORE = 8.0
MAX_STORIES_PER_COUNTRY = 3
MAX_STORIES_PER_SOURCE = 2

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "Chrome/150 Safari/537.36"
)


# ==========================================================
# NEWS SEARCHES
# ==========================================================

NEWS_SEARCHES = [
    "West Africa politics when:1d",
    "West Africa economy when:1d",
    "West Africa security when:1d",
    "ECOWAS when:1d",
    "Nigeria politics economy when:1d",
    "Ghana economy politics when:1d",
    "Senegal politics economy when:1d",
    "Cote d'Ivoire economy politics when:1d",
    "Sahel security when:1d",
    "West Africa investment business when:1d",
    "West Africa climate agriculture when:1d",
    "Mali Burkina Faso Niger security politics when:1d",
]


# ==========================================================
# GEOGRAPHIC RELEVANCE
# ==========================================================

COUNTRY_KEYWORDS = {
    "Benin": ["benin", "beninese"],
    "Burkina Faso": ["burkina faso", "burkinabe", "burkinabè"],
    "Cabo Verde": ["cabo verde", "cape verde", "cape verdean"],
    "Côte d'Ivoire": [
        "cote d'ivoire",
        "côte d'ivoire",
        "ivory coast",
        "ivorian",
    ],
    "The Gambia": ["the gambia", "gambia", "gambian"],
    "Ghana": ["ghana", "ghanaian"],
    "Guinea": ["guinea", "guinean"],
    "Guinea-Bissau": ["guinea-bissau", "guinea bissau", "bissau-guinean"],
    "Liberia": ["liberia", "liberian"],
    "Mali": ["mali", "malian"],
    "Mauritania": ["mauritania", "mauritanian"],
    "Niger": ["niger", "nigerien"],
    "Nigeria": ["nigeria", "nigerian"],
    "Senegal": ["senegal", "senegalese"],
    "Sierra Leone": ["sierra leone", "sierra leonean"],
    "Togo": ["togo", "togolese"],
}

REGIONAL_KEYWORDS = [
    "west africa",
    "western africa",
    "ecowas",
    "sahel",
    "gulf of guinea",
    "francophone africa",
    "west african",
]

STRONG_RELEVANCE_TERMS = [
    "ecowas",
    "west africa",
    "western africa",
    "sahel",
    "gulf of guinea",
]

WEAK_CONTEXT_TERMS = [
    "africa",
    "african",
]


# ==========================================================
# CATEGORY KEYWORDS
# ==========================================================

CATEGORY_KEYWORDS = {
    "Security": [
        "security",
        "military",
        "army",
        "attack",
        "terrorism",
        "terrorist",
        "militant",
        "insurgent",
        "conflict",
        "violence",
        "coup",
        "border",
        "kidnap",
        "jihadist",
        "peacekeeping",
        "armed group",
    ],
    "Economy": [
        "economy",
        "economic",
        "inflation",
        "currency",
        "debt",
        "finance",
        "fiscal",
        "interest rate",
        "central bank",
        "gdp",
        "budget",
        "imf",
        "world bank",
        "tax",
        "subsidy",
    ],
    "Politics": [
        "politics",
        "political",
        "election",
        "president",
        "government",
        "minister",
        "parliament",
        "democracy",
        "opposition",
        "constitution",
        "ecowas",
        "diplomatic",
        "sanctions",
        "cabinet",
        "governance",
    ],
    "Business": [
        "business",
        "investment",
        "company",
        "industry",
        "trade",
        "startup",
        "technology",
        "telecom",
        "bank",
        "market",
        "infrastructure",
        "energy",
        "mining",
        "oil",
        "gas",
        "manufacturing",
    ],
    "Climate": [
        "climate",
        "flood",
        "flooding",
        "drought",
        "weather",
        "rainfall",
        "agriculture",
        "food security",
        "environment",
        "heat",
        "harvest",
        "crop",
    ],
    "Society": [
        "society",
        "education",
        "health",
        "migration",
        "protest",
        "community",
        "population",
        "employment",
        "poverty",
        "humanitarian",
        "refugee",
        "displacement",
        "strike",
    ],
}


# ==========================================================
# INTELLIGENCE SCORING KEYWORDS
# ==========================================================

INTELLIGENCE_SCORE_TERMS = {
    "political": {
        "election": 8, "president": 5, "government": 5, "minister": 4,
        "parliament": 5, "opposition": 5, "constitution": 7, "coup": 10,
        "sanctions": 7, "ecowas": 6, "diplomatic": 4, "governance": 4,
        "protest": 5, "state of emergency": 8, "cabinet": 4,
    },
    "economic": {
        "inflation": 8, "currency": 8, "debt": 8, "default": 10,
        "imf": 7, "world bank": 5, "central bank": 7, "interest rate": 6,
        "budget": 6, "tax": 5, "subsidy": 6, "gdp": 5, "investment": 4,
        "trade": 4, "oil": 4, "gas": 4, "mining": 4, "energy": 4,
    },
    "security": {
        "attack": 9, "terrorist": 10, "terrorism": 10, "militant": 8,
        "insurgent": 9, "military": 6, "army": 5, "conflict": 7,
        "violence": 6, "kidnap": 8, "jihadist": 10, "armed group": 8,
        "border closure": 7, "peacekeeping": 5, "coup": 8,
    },
    "regional": {
        "ecowas": 10, "west africa": 9, "sahel": 8, "gulf of guinea": 7,
        "regional": 5, "cross-border": 7, "sanctions": 6, "refugee": 6,
        "displacement": 5, "trade corridor": 6, "border": 5,
    },
}

CATEGORY_PRIORITY_ORDER = [
    "Security", "Economy", "Politics", "Business", "Climate", "Society"
]

# ==========================================================
# SOURCE QUALITY
# ==========================================================

SOURCE_QUALITY_SCORES = {
    # International wire services and high-reliability reporting
    "Reuters": 10,
    "Associated Press": 10,
    "AP News": 10,
    "Agence France-Presse": 9,
    "AFP": 9,

    # Major international outlets
    "BBC": 9,
    "BBC News": 9,
    "Financial Times": 9,
    "Bloomberg": 9,
    "The Guardian": 8,
    "Al Jazeera": 8,
    "France 24": 8,
    "Deutsche Welle": 8,
    "DW": 8,
    "Voice of America": 7,
    "VOA": 7,

    # Specialist and regional outlets
    "The Africa Report": 8,
    "Africanews": 7,
    "Africa News": 7,
    "Jeune Afrique": 8,
    "BusinessDay": 7,
    "Premium Times": 8,
    "Daily Trust": 7,
    "ThisDay": 7,
    "TheCable": 7,
    "Channels Television": 7,
    "Punch Newspapers": 6,
    "Vanguard": 6,
    "Leadership News": 6,
    "Graphic Online": 7,
    "GhanaWeb": 6,
    "MyJoyOnline": 7,
    "Citi Newsroom": 7,
    "The Point": 6,
    "Sierra Leone Telegraph": 6,
    "Liberian Observer": 6,

    # Institutional sources
    "ECOWAS": 9,
    "African Union": 9,
    "International Monetary Fund": 9,
    "IMF": 9,
    "World Bank": 9,
    "United Nations": 9,
    "UN News": 9,
}

LOW_QUALITY_SOURCE_TERMS = [
    "yahoo",
    "msn",
    "newsbreak",
    "medium",
    "substack",
    "blogspot",
    "wordpress",
    "press release",
    "pr newswire",
    "globenewswire",
    "ein presswire",
]

UNSUITABLE_STORY_TERMS = [
    # Sport
    "premier league",
    "champions league",
    "football",
    "soccer",
    "afcon qualifier",
    "transfer news",
    "match preview",
    "match report",
    "fixture",
    "goalkeeper",
    "striker",

    # Entertainment and celebrity
    "celebrity",
    "actor",
    "actress",
    "singer",
    "album",
    "music video",
    "box office",
    "reality tv",
    "fashion show",

    # Travel, lifestyle and consumer content
    "travel guide",
    "tourist destination",
    "holiday destination",
    "best beaches",
    "recipe",
    "restaurant review",
    "horoscope",
    "lottery",
]


# ==========================================================
# POLITICAL-RISK IMPORTANCE
# ==========================================================

IMPORTANT_TERMS = {
    "election": 5,
    "coup": 7,
    "president": 3,
    "government": 3,
    "ecowas": 6,
    "inflation": 4,
    "debt": 4,
    "default": 6,
    "imf": 4,
    "attack": 5,
    "military": 4,
    "security": 3,
    "investment": 3,
    "trade": 3,
    "energy": 3,
    "currency": 4,
    "central bank": 4,
    "protest": 4,
    "strike": 3,
    "flood": 3,
    "food security": 4,
    "sanctions": 5,
    "constitutional": 4,
    "insurgent": 5,
    "terrorist": 5,
    "kidnap": 5,
    "border closure": 5,
    "state of emergency": 6,
    "refugee": 3,
    "displacement": 3,
    "mining": 3,
    "oil": 3,
    "gas": 3,
    "power outage": 3,
}


# ==========================================================
# BASIC TEXT HELPERS
# ==========================================================

def clean_text(value: str | None) -> str:
    """Remove HTML, repeated whitespace and encoded characters."""

    if not value:
        return ""

    value = html.unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalise_text(value: str) -> str:
    """Create simplified text for matching and duplicate detection."""

    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def contains_phrase(text: str, phrase: str) -> bool:
    """Match complete normalised words or phrases."""

    normalised_text = f" {normalise_text(text)} "
    normalised_phrase = normalise_text(phrase)

    if not normalised_phrase:
        return False

    return f" {normalised_phrase} " in normalised_text


def create_story_id(title: str, url: str) -> str:
    """Create a stable identifier for a news story."""

    raw_value = f"{normalise_text(title)}|{url}"

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()[:16]


def story_searchable_text(story: dict[str, Any]) -> str:
    """Return article text without contaminating it with the RSS query."""

    return normalise_text(
        " ".join(
            [
                story.get("title", ""),
                story.get("summary", ""),
            ]
        )
    )


# ==========================================================
# GOOGLE NEWS RSS
# ==========================================================

def build_google_news_url(search_term: str) -> str:
    """Build a Google News RSS URL for an English-language search."""

    encoded_query = urllib.parse.quote_plus(search_term)

    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        "&hl=en-GB"
        "&gl=GB"
        "&ceid=GB:en"
    )


def download_feed(url: str) -> bytes:
    """Download one RSS feed and return its raw XML bytes."""

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml,"
                "application/xml,"
                "text/xml,"
                "*/*"
            ),
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        return response.read()


def parse_publication_date(value: str | None) -> str:
    """Convert an RSS publication date into UTC ISO format."""

    if not value:
        return ""

    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
    ]

    for date_format in formats:
        try:
            parsed = datetime.strptime(
                value.strip(),
                date_format,
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed.astimezone(
                timezone.utc
            ).isoformat()

        except ValueError:
            continue

    return ""


def split_google_news_title(
    raw_title: str,
) -> tuple[str, str]:
    """Separate a Google News headline from its publisher."""

    title = clean_text(raw_title)

    if " - " not in title:
        return title, "Unknown source"

    article_title, publisher = title.rsplit(
        " - ",
        1,
    )

    return (
        article_title.strip(),
        publisher.strip(),
    )


def parse_feed(
    xml_data: bytes,
    search_term: str,
) -> list[dict[str, Any]]:
    """Parse one RSS feed into story dictionaries."""

    root = ET.fromstring(xml_data)
    stories: list[dict[str, Any]] = []

    for item in root.findall(".//item"):
        raw_title = item.findtext(
            "title",
            default="",
        )

        title, source = split_google_news_title(
            raw_title
        )

        url = clean_text(
            item.findtext(
                "link",
                default="",
            )
        )

        description = clean_text(
            item.findtext(
                "description",
                default="",
            )
        )

        publication_date = parse_publication_date(
            item.findtext(
                "pubDate",
                default="",
            )
        )

        if not title or not url:
            continue

        stories.append(
            {
                "id": create_story_id(
                    title,
                    url,
                ),
                "title": title,
                "summary": description,
                "url": url,
                "source": source,
                "published_at": publication_date,
                "search_term": search_term,
            }
        )

    return stories


def collect_news_stories() -> list[dict[str, Any]]:
    """Download and combine all configured Google News searches."""

    collected: list[dict[str, Any]] = []
    successful_feeds = 0

    for search_term in NEWS_SEARCHES:
        feed_url = build_google_news_url(
            search_term
        )

        print(f"Collecting: {search_term}")

        try:
            xml_data = download_feed(
                feed_url
            )

            feed_stories = parse_feed(
                xml_data,
                search_term,
            )

            collected.extend(
                feed_stories
            )

            successful_feeds += 1

            print(
                f"  Found {len(feed_stories)} stories"
            )

        except (
            urllib.error.URLError,
            TimeoutError,
            ET.ParseError,
            OSError,
        ) as error:
            print(
                f"  Skipped feed: {error}"
            )

    print()
    print(
        f"Feeds completed: {successful_feeds}/{len(NEWS_SEARCHES)}"
    )
    print(
        f"Collected {len(collected)} raw stories"
    )

    return collected


# ==========================================================
# FRESHNESS
# ==========================================================

def parsed_publication_datetime(
    story: dict[str, Any],
) -> datetime | None:
    """Return the publication date as a UTC datetime."""

    value = story.get("published_at", "")

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except (ValueError, TypeError):
        return None


def story_age_hours(
    story: dict[str, Any],
) -> float | None:
    """Return the age of a story in hours."""

    published = parsed_publication_datetime(
        story
    )

    if published is None:
        return None

    age = datetime.now(
        timezone.utc
    ) - published

    return age.total_seconds() / 3600


def story_is_recent(
    story: dict[str, Any],
    maximum_age_hours: int = MAX_STORY_AGE_HOURS,
) -> bool:
    """Return True only for valid, recent publication dates."""

    age_hours = story_age_hours(
        story
    )

    if age_hours is None:
        return False

    return -2 <= age_hours <= maximum_age_hours


def recency_score(
    story: dict[str, Any],
) -> float:
    """Reward newer stories without overwhelming importance scoring."""

    age_hours = story_age_hours(
        story
    )

    if age_hours is None:
        return 0.0

    if age_hours <= 6:
        return 5.0

    if age_hours <= 12:
        return 4.0

    if age_hours <= 24:
        return 3.0

    if age_hours <= 30:
        return 2.0

    return 1.0


def publication_timestamp(
    story: dict[str, Any],
) -> float:
    """Return a sortable publication timestamp."""

    published = parsed_publication_datetime(
        story
    )

    return published.timestamp() if published else 0.0


# ==========================================================
# RELEVANCE AND CLASSIFICATION
# ==========================================================

def detect_country(
    story: dict[str, Any],
) -> str:
    """Detect the most likely West African country."""

    searchable_text = story_searchable_text(
        story
    )

    best_country = "Regional"
    best_score = 0

    title_text = normalise_text(
        story.get("title", "")
    )

    for country_name, keywords in COUNTRY_KEYWORDS.items():
        country_score = 0

        for keyword in keywords:
            if contains_phrase(title_text, keyword):
                country_score += 3
            elif contains_phrase(searchable_text, keyword):
                country_score += 1

        if country_score > best_score:
            best_score = country_score
            best_country = country_name

    return best_country


def west_africa_relevance_score(
    story: dict[str, Any],
) -> int:
    """Measure whether a story is genuinely about West Africa."""

    title_text = normalise_text(
        story.get("title", "")
    )
    full_text = story_searchable_text(
        story
    )

    score = 0

    for phrase in STRONG_RELEVANCE_TERMS:
        if contains_phrase(title_text, phrase):
            score += 5
        elif contains_phrase(full_text, phrase):
            score += 3

    country_hits = 0

    for keywords in COUNTRY_KEYWORDS.values():
        country_found = False

        for keyword in keywords:
            if contains_phrase(title_text, keyword):
                score += 4
                country_found = True
                break

            if contains_phrase(full_text, keyword):
                score += 2
                country_found = True
                break

        if country_found:
            country_hits += 1

    if country_hits >= 2:
        score += 2

    if any(
        contains_phrase(full_text, term)
        for term in WEAK_CONTEXT_TERMS
    ):
        score += 1

    return score


def story_is_unsuitable(
    story: dict[str, Any],
) -> bool:
    """Reject sport, entertainment, travel and similar content."""

    searchable_text = story_searchable_text(
        story
    )

    return any(
        contains_phrase(
            searchable_text,
            term,
        )
        for term in UNSUITABLE_STORY_TERMS
    )


def detect_category(
    story: dict[str, Any],
) -> str:
    """Classify from article text only, never from the RSS search phrase."""

    title_text = normalise_text(story.get("title", ""))
    summary_text = normalise_text(story.get("summary", ""))
    category_scores: dict[str, int] = {}

    for category_name, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            if contains_phrase(title_text, keyword):
                score += 4
            if contains_phrase(summary_text, keyword):
                score += 1
        category_scores[category_name] = score

    highest = max(category_scores.values(), default=0)
    if highest == 0:
        return "Business"

    tied = {name for name, score in category_scores.items() if score == highest}
    for category in CATEGORY_PRIORITY_ORDER:
        if category in tied:
            return category

    return "Business"


# ==========================================================
# SOURCE EVALUATION
# ==========================================================

def normalise_source_name(
    source: str,
) -> str:
    """Clean common publisher-name variations."""

    cleaned = clean_text(source)

    replacements = {
        "BBC.com": "BBC News",
        "Reuters.com": "Reuters",
        "AP": "AP News",
        "The Guardian Nigeria News": "The Guardian Nigeria",
    }

    return replacements.get(
        cleaned,
        cleaned,
    )


def source_quality_score(
    source: str,
) -> int:
    """Score known publishers and penalise weak aggregators."""

    source_text = normalise_text(
        source
    )

    if not source_text:
        return 2

    for weak_term in LOW_QUALITY_SOURCE_TERMS:
        if contains_phrase(source_text, weak_term):
            return 1

    best_score = 0

    for publisher, score in SOURCE_QUALITY_SCORES.items():
        if contains_phrase(
            source_text,
            publisher,
        ):
            best_score = max(
                best_score,
                score,
            )

    if best_score:
        return best_score

    return 4


# ==========================================================
# STORY SCORING
# ==========================================================

def dimension_score(
    story: dict[str, Any],
    dimension: str,
) -> int:
    """Score one intelligence dimension on a transparent 0-100 scale."""

    title = normalise_text(story.get("title", ""))
    summary = normalise_text(story.get("summary", ""))
    raw_score = 0.0

    for term, weight in INTELLIGENCE_SCORE_TERMS[dimension].items():
        if contains_phrase(title, term):
            raw_score += weight * 1.5
        elif contains_phrase(summary, term):
            raw_score += weight

    if dimension == "regional":
        countries_mentioned = 0
        combined = f"{title} {summary}"
        for keywords in COUNTRY_KEYWORDS.values():
            if any(contains_phrase(combined, keyword) for keyword in keywords):
                countries_mentioned += 1
        if countries_mentioned >= 2:
            raw_score += min(18, countries_mentioned * 4)
        if story.get("country") == "Regional":
            raw_score += 8

    return max(0, min(100, round(raw_score * 2.2)))


def confidence_score(story: dict[str, Any]) -> int:
    """Estimate confidence from publisher quality and available evidence."""

    score = 35
    score += source_quality_score(story.get("source", "")) * 5
    if story.get("published_at"):
        score += 6
    summary_length = len(clean_text(story.get("summary", "")))
    if summary_length >= 100:
        score += 8
    elif summary_length >= 40:
        score += 4
    if story.get("country") != "Regional":
        score += 3
    return max(30, min(95, score))


def priority_label(score: float) -> str:
    """Turn a numerical priority score into a simple analyst label."""

    if score >= 75:
        return "Critical"
    if score >= 55:
        return "High"
    if score >= 35:
        return "Moderate"
    return "Low"


def apply_intelligence_scores(story: dict[str, Any]) -> None:
    """Add all Phase 2 intelligence scores to a story in place."""

    political = dimension_score(story, "political")
    economic = dimension_score(story, "economic")
    security = dimension_score(story, "security")
    regional = dimension_score(story, "regional")
    confidence = confidence_score(story)

    dimensions = [political, economic, security, regional]
    highest = max(dimensions)
    breadth = sum(1 for value in dimensions if value >= 25)

    priority = (
        highest * 0.55
        + sum(dimensions) / 4 * 0.25
        + confidence * 0.12
        + min(8, breadth * 2)
    )
    priority = round(min(100, priority), 1)

    story["political_score"] = political
    story["economic_score"] = economic
    story["security_score"] = security
    story["regional_impact_score"] = regional
    story["confidence_score"] = confidence
    story["intelligence_priority_score"] = priority
    story["priority_level"] = priority_label(priority)


def story_importance_score(
    story: dict[str, Any],
) -> float:
    """Keep the existing ranking field while using the new intelligence model."""

    base = story.get("intelligence_priority_score", 0)
    quality_bonus = source_quality_score(story.get("source", "")) * 0.6
    recency_bonus = recency_score(story)
    relevance_bonus = min(int(story.get("relevance_score", 0)), 12) * 0.35
    return round(base + quality_bonus + recency_bonus + relevance_bonus, 3)


# ==========================================================
# DUPLICATE REMOVAL
# ==========================================================

def title_word_set(
    title: str,
) -> set[str]:
    """Convert a title into a set of meaningful words."""

    ignored_words = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "in",
        "on",
        "for",
        "with",
        "as",
        "at",
        "by",
        "from",
        "after",
        "over",
        "new",
        "says",
        "report",
        "reports",
        "west",
        "africa",
        "african",
    }

    return {
        word
        for word in normalise_text(title).split()
        if len(word) > 2 and word not in ignored_words
    }


def titles_are_similar(
    first_title: str,
    second_title: str,
) -> bool:
    """Compare two titles using symmetric word overlap."""

    first_words = title_word_set(
        first_title
    )
    second_words = title_word_set(
        second_title
    )

    if not first_words or not second_words:
        return False

    overlap = len(
        first_words.intersection(
            second_words
        )
    )

    smaller_size = min(
        len(first_words),
        len(second_words),
    )

    larger_size = max(
        len(first_words),
        len(second_words),
    )

    containment = overlap / smaller_size
    jaccard = overlap / len(
        first_words.union(
            second_words
        )
    )

    return (
        containment >= 0.68
        or (
            containment >= 0.55
            and jaccard >= 0.42
            and larger_size >= 4
        )
    )


def canonical_url(
    url: str,
) -> str:
    """Remove fragments and common tracking parameters."""

    try:
        parsed = urllib.parse.urlsplit(
            url
        )

        query_pairs = urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )

        filtered_query = urllib.parse.urlencode(
            [
                (key, value)
                for key, value in query_pairs
                if not key.lower().startswith(
                    "utm_"
                )
                and key.lower()
                not in {
                    "gclid",
                    "fbclid",
                    "mc_cid",
                    "mc_eid",
                }
            ]
        )

        return urllib.parse.urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                filtered_query,
                "",
            )
        )

    except ValueError:
        return url.strip()


def better_duplicate_story(
    first_story: dict[str, Any],
    second_story: dict[str, Any],
) -> dict[str, Any]:
    """Choose the strongest report of the same event."""

    first_key = (
        source_quality_score(
            first_story.get("source", "")
        ),
        first_story.get(
            "importance_score",
            0,
        ),
        publication_timestamp(
            first_story
        ),
    )

    second_key = (
        source_quality_score(
            second_story.get("source", "")
        ),
        second_story.get(
            "importance_score",
            0,
        ),
        publication_timestamp(
            second_story
        ),
    )

    if second_key > first_key:
        return second_story

    return first_story


def remove_duplicate_stories(
    stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate while preserving the best available report."""

    unique_stories: list[dict[str, Any]] = []
    exact_url_positions: dict[str, int] = {}
    duplicates_removed = 0
    upgrades_made = 0

    for story in stories:
        url = canonical_url(
            story.get("url", "")
        )

        if not url:
            continue

        story["canonical_url"] = url

        if url in exact_url_positions:
            position = exact_url_positions[
                url
            ]

            preferred = better_duplicate_story(
                unique_stories[position],
                story,
            )

            if preferred is story:
                unique_stories[position] = story
                upgrades_made += 1

            duplicates_removed += 1
            continue

        similar_position: int | None = None

        for index, existing_story in enumerate(
            unique_stories
        ):
            if titles_are_similar(
                story.get("title", ""),
                existing_story.get(
                    "title",
                    "",
                ),
            ):
                similar_position = index
                break

        if similar_position is not None:
            preferred = better_duplicate_story(
                unique_stories[
                    similar_position
                ],
                story,
            )

            if preferred is story:
                old_url = unique_stories[
                    similar_position
                ].get(
                    "canonical_url",
                    "",
                )

                if old_url:
                    exact_url_positions.pop(
                        old_url,
                        None,
                    )

                unique_stories[
                    similar_position
                ] = story

                exact_url_positions[
                    url
                ] = similar_position

                upgrades_made += 1

            duplicates_removed += 1
            continue

        exact_url_positions[
            url
        ] = len(
            unique_stories
        )

        unique_stories.append(
            story
        )

    print(
        f"{len(unique_stories)} stories remain after deduplication"
    )
    print(
        f"  Duplicate reports removed: {duplicates_removed}"
    )
    print(
        f"  Better-source replacements: {upgrades_made}"
    )

    return unique_stories


# ==========================================================
# CLASSIFY AND RANK
# ==========================================================

def classify_and_rank_stories(
    stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter, classify, deduplicate and rank candidate stories."""

    recent_stories = [
        story
        for story in stories
        if story_is_recent(
            story
        )
    ]

    print()
    print(
        f"{len(recent_stories)} stories remain after "
        f"the {MAX_STORY_AGE_HOURS}-hour age filter"
    )

    unsuitable_count = 0
    weak_relevance_count = 0
    low_score_count = 0
    classified: list[dict[str, Any]] = []

    for story in recent_stories:
        enriched_story = dict(
            story
        )

        enriched_story["source"] = (
            normalise_source_name(
                enriched_story.get(
                    "source",
                    "",
                )
            )
        )

        if story_is_unsuitable(
            enriched_story
        ):
            unsuitable_count += 1
            continue

        relevance_score = (
            west_africa_relevance_score(
                enriched_story
            )
        )

        if relevance_score < MIN_RELEVANCE_SCORE:
            weak_relevance_count += 1
            continue

        enriched_story[
            "relevance_score"
        ] = relevance_score

        enriched_story["country"] = detect_country(
            enriched_story
        )

        enriched_story["category"] = detect_category(
            enriched_story
        )

        enriched_story[
            "source_quality_score"
        ] = source_quality_score(
            enriched_story.get(
                "source",
                "",
            )
        )

        apply_intelligence_scores(
            enriched_story
        )

        enriched_story[
            "importance_score"
        ] = story_importance_score(
            enriched_story
        )

        if (
            enriched_story[
                "importance_score"
            ]
            < MIN_FINAL_SCORE
        ):
            low_score_count += 1
            continue

        classified.append(
            enriched_story
        )

    print(
        f"{len(classified)} stories pass relevance and quality checks"
    )
    print(
        f"  Unsuitable topics rejected: {unsuitable_count}"
    )
    print(
        f"  Weak West Africa relevance rejected: {weak_relevance_count}"
    )
    print(
        f"  Below minimum collection score: {low_score_count}"
    )

    unique_stories = remove_duplicate_stories(
        classified
    )

    ranked_stories = sorted(
        unique_stories,
        key=lambda story: (
            story.get(
                "importance_score",
                0,
            ),
            story.get(
                "source_quality_score",
                0,
            ),
            publication_timestamp(
                story
            ),
        ),
        reverse=True,
    )

    return ranked_stories


# ==========================================================
# BALANCED STORY SELECTION
# ==========================================================

CATEGORY_TARGETS = {
    "Politics": 2,
    "Economy": 2,
    "Security": 2,
    "Business": 1,
    "Society": 1,
    "Climate": 1,
}


def story_can_be_selected(
    story: dict[str, Any],
    country_counts: dict[str, int],
    source_counts: dict[str, int],
    country_limit: int,
) -> bool:
    """Apply country and publisher diversity limits."""

    story_country = story.get(
        "country",
        "Regional",
    )
    story_source = story.get(
        "source",
        "Unknown source",
    )

    if country_counts.get(
        story_country,
        0,
    ) >= country_limit:
        return False

    if source_counts.get(
        story_source,
        0,
    ) >= MAX_STORIES_PER_SOURCE:
        return False

    return True


def add_selected_story(
    story: dict[str, Any],
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    country_counts: dict[str, int],
    source_counts: dict[str, int],
) -> None:
    """Add one story and update selection counters."""

    selected.append(
        story
    )

    selected_ids.add(
        story.get(
            "id",
            "",
        )
    )

    country = story.get(
        "country",
        "Regional",
    )
    source = story.get(
        "source",
        "Unknown source",
    )

    country_counts[country] = (
        country_counts.get(
            country,
            0,
        )
        + 1
    )

    source_counts[source] = (
        source_counts.get(
            source,
            0,
        )
        + 1
    )


def select_balanced_stories(
    ranked_stories: list[dict[str, Any]],
    limit: int = NUMBER_OF_STORIES,
) -> list[dict[str, Any]]:
    """Select a varied briefing without sacrificing overall quality."""

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    country_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}

    category_counts: dict[str, int] = {
        category: 0
        for category in CATEGORY_TARGETS
    }

    for category, target in CATEGORY_TARGETS.items():
        for story in ranked_stories:
            if len(selected) >= limit:
                break

            story_id = story.get(
                "id",
                "",
            )

            if story_id in selected_ids:
                continue

            if story.get(
                "category"
            ) != category:
                continue

            if not story_can_be_selected(
                story,
                country_counts,
                source_counts,
                country_limit=2,
            ):
                continue

            add_selected_story(
                story,
                selected,
                selected_ids,
                country_counts,
                source_counts,
            )

            category_counts[category] += 1

            if category_counts[
                category
            ] >= target:
                break

    for story in ranked_stories:
        if len(selected) >= limit:
            break

        story_id = story.get(
            "id",
            "",
        )

        if story_id in selected_ids:
            continue

        if not story_can_be_selected(
            story,
            country_counts,
            source_counts,
            country_limit=MAX_STORIES_PER_COUNTRY,
        ):
            continue

        add_selected_story(
            story,
            selected,
            selected_ids,
            country_counts,
            source_counts,
        )

    selected.sort(
        key=lambda story: (
            story.get(
                "importance_score",
                0,
            ),
            publication_timestamp(
                story
            ),
        ),
        reverse=True,
    )

    print()
    print(
        f"Selected {len(selected[:limit])} final stories"
    )

    return selected[:limit]


# ==========================================================
# SUMMARY CLEANING
# ==========================================================

def shorten_text(
    value: str,
    maximum_length: int = 320,
) -> str:
    """Shorten text cleanly without cutting through a word."""

    value = clean_text(
        value
    )

    if len(value) <= maximum_length:
        return value

    shortened = value[
        :maximum_length
    ].rsplit(
        " ",
        1,
    )[0]

    return shortened.rstrip(
        ".,;:"
    ) + "…"


def create_story_summary(
    story: dict[str, Any],
) -> str:
    """Build a concise summary from the RSS description."""

    description = clean_text(
        story.get(
            "summary",
            "",
        )
    )

    title = clean_text(
        story.get(
            "title",
            "",
        )
    )

    if description:
        description = re.sub(
            r"\s*-\s*[^-]{2,80}$",
            "",
            description,
        )

        return shorten_text(
            description,
            maximum_length=340,
        )

    if title:
        return (
            f"This development concerns "
            f"{title.lower()}."
        )

    return (
        "No summary is available for this story."
    )


# ==========================================================
# EXECUTIVE SUMMARY
# ==========================================================

def category_summary(
    stories: list[dict[str, Any]],
) -> str:
    """Describe the most prominent briefing categories."""

    counts: dict[str, int] = {}

    for story in stories:
        category = story.get(
            "category",
            "General",
        )

        counts[category] = (
            counts.get(
                category,
                0,
            )
            + 1
        )

    ordered_categories = sorted(
        counts.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    category_names = [
        name.lower()
        for name, _ in ordered_categories[:3]
    ]

    if not category_names:
        return "regional developments"

    if len(category_names) == 1:
        return category_names[0]

    if len(category_names) == 2:
        return (
            f"{category_names[0]} and "
            f"{category_names[1]}"
        )

    return (
        f"{category_names[0]}, "
        f"{category_names[1]} and "
        f"{category_names[2]}"
    )


def create_executive_summary(
    stories: list[dict[str, Any]],
) -> str:
    """Generate a concise overview from selected stories."""

    if not stories:
        return (
            "No suitable stories were available for today's "
            "West Africa briefing."
        )

    named_countries: list[str] = []

    for story in stories:
        country = story.get(
            "country",
            "Regional",
        )

        if (
            country != "Regional"
            and country not in named_countries
        ):
            named_countries.append(
                country
            )

    country_text = ", ".join(
        named_countries[:4]
    )

    themes = category_summary(
        stories
    )

    opening = (
        "Today's West Africa briefing is shaped primarily by "
        f"{themes}."
    )

    if country_text:
        opening += (
            " Significant developments are concentrated in "
            f"{country_text}."
        )

    security_count = sum(
        1
        for story in stories
        if story.get(
            "category"
        ) == "Security"
    )

    economy_count = sum(
        1
        for story in stories
        if story.get(
            "category"
        ) == "Economy"
    )

    closing_parts: list[str] = []

    if security_count:
        closing_parts.append(
            "security pressures remain an important source "
            "of political and humanitarian risk"
        )

    if economy_count:
        closing_parts.append(
            "economic policy and market conditions continue "
            "to influence investor confidence and household welfare"
        )

    if closing_parts:
        opening += (
            " "
            + "; while ".join(
                closing_parts
            )
            + "."
        )

    return shorten_text(
        opening,
        maximum_length=520,
    )


# ==========================================================
# DAILY LEARNING POINT
# ==========================================================

LEARNING_POINTS = [
    {
        "type": "Regional institution",
        "title": "What is ECOWAS?",
        "description": (
            "The Economic Community of West African States "
            "was created to promote regional economic integration. "
            "It has also developed important political and security "
            "roles, including mediation, election monitoring and "
            "responses to unconstitutional changes of government."
        ),
    },
    {
        "type": "Political risk concept",
        "title": "Why currency instability matters",
        "description": (
            "Sharp currency movements can increase import costs, "
            "raise inflation and make foreign-currency debt harder "
            "to service. They can therefore affect public finances, "
            "business confidence and political stability."
        ),
    },
    {
        "type": "Regional security",
        "title": "Understanding the central Sahel",
        "description": (
            "The central Sahel commonly refers to Mali, Burkina Faso "
            "and Niger. The area has experienced persistent militant "
            "violence, military intervention in politics and severe "
            "humanitarian pressure."
        ),
    },
    {
        "type": "Economic development",
        "title": "Why infrastructure affects industrial growth",
        "description": (
            "Reliable electricity, roads, railways and ports reduce "
            "production and trading costs. Weak infrastructure can "
            "therefore limit manufacturing growth even where labour "
            "and natural resources are available."
        ),
    },
    {
        "type": "Political economy",
        "title": "What fiscal reform means",
        "description": (
            "Fiscal reform involves changing government spending, "
            "taxation or borrowing to improve public finances. "
            "Although reforms may increase long-term stability, they "
            "can create short-term political pressure when subsidies "
            "are reduced or taxes rise."
        ),
    },
]


def choose_learning_point() -> dict[str, str]:
    """Rotate the learning point by UTC day of year."""

    day_number = datetime.now(
        timezone.utc
    ).timetuple().tm_yday

    index = day_number % len(
        LEARNING_POINTS
    )

    return LEARNING_POINTS[
        index
    ]


# ==========================================================
# FINAL OUTPUT
# ==========================================================

def prepare_story_for_output(
    story: dict[str, Any],
    rank: int,
) -> dict[str, Any]:
    """Convert an internal story into the website JSON structure."""

    return {
        "rank": rank,
        "id": story.get(
            "id",
            "",
        ),
        "title": clean_text(
            story.get(
                "title",
                "",
            )
        ),
        "summary": create_story_summary(
            story
        ),
        "source": clean_text(
            story.get(
                "source",
                "Unknown source",
            )
        ),
        "url": story.get(
            "url",
            "",
        ),
        "published_at": story.get(
            "published_at",
            "",
        ),
        "country": story.get(
            "country",
            "Regional",
        ),
        "category": story.get(
            "category",
            "Politics",
        ),
        "importance_score": round(
            float(story.get("importance_score", 0)),
            2,
        ),
        "political_score": int(story.get("political_score", 0)),
        "economic_score": int(story.get("economic_score", 0)),
        "security_score": int(story.get("security_score", 0)),
        "regional_impact_score": int(story.get("regional_impact_score", 0)),
        "confidence_score": int(story.get("confidence_score", 0)),
        "intelligence_priority_score": round(
            float(story.get("intelligence_priority_score", 0)), 1
        ),
        "priority_level": story.get("priority_level", "Low"),
    }


def build_briefing(
    selected_stories: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the complete briefing.json object."""

    prepared_stories = [
        prepare_story_for_output(
            story,
            rank=index,
        )
        for index, story in enumerate(
            selected_stories,
            start=1,
        )
    ]

    source_names = sorted(
        {
            story["source"]
            for story in prepared_stories
            if story["source"]
        }
    )

    countries = sorted(
        {
            story["country"]
            for story in prepared_stories
            if story["country"] != "Regional"
        }
    )

    categories = sorted(
        {
            story["category"]
            for story in prepared_stories
        }
    )

    generated_at = datetime.now(
        timezone.utc
    )

    return {
        "date": generated_at.date().isoformat(),
        "generated_at": generated_at.isoformat(),
        "title": "West Africa Daily Intelligence Brief",
        "executive_summary": create_executive_summary(
            prepared_stories
        ),
        "statistics": {
            "story_count": len(
                prepared_stories
            ),
            "source_count": len(
                source_names
            ),
            "country_count": len(
                countries
            ),
            "category_count": len(
                categories
            ),
        },
        "sources": source_names,
        "countries": countries,
        "categories": categories,
        "stories": prepared_stories,
        "learning": choose_learning_point(),
        "methodology": (
            "Stories are collected from public Google News RSS "
            "searches, checked for freshness and West Africa relevance, "
            "filtered for unsuitable topics and near-duplicates, then "
            "ranked using publisher quality, recency and transparent political, "
            "economic, security and regional-impact scores. When several "
            "outlets report the same event, "
            "the strongest available source is retained."
        ),
    }


# ==========================================================
# SAFE FILE WRITING
# ==========================================================

def write_json_safely(
    output_path: Path,
    data: dict[str, Any],
) -> None:
    """Write to a temporary file before replacing briefing.json."""

    temporary_path = output_path.with_suffix(
        ".json.tmp"
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write(
            "\n"
        )

    temporary_path.replace(
        output_path
    )


# ==========================================================
# DIAGNOSTICS
# ==========================================================

def print_selected_story_report(
    stories: list[dict[str, Any]],
) -> None:
    """Print an audit-friendly list of selected stories."""

    print()
    print("Final briefing selection")
    print("-" * 60)

    for index, story in enumerate(
        stories,
        start=1,
    ):
        age = story_age_hours(
            story
        )

        age_text = (
            f"{age:.1f}h old"
            if age is not None
            else "unknown age"
        )

        print(
            f"{index:>2}. [{story.get('category', 'General')}] "
            f"{story.get('title', '')}"
        )
        print(
            f"    {story.get('source', 'Unknown source')} | "
            f"{story.get('country', 'Regional')} | "
            f"score {story.get('importance_score', 0):.2f} | "
            f"{age_text}"
        )


# ==========================================================
# MAIN PROGRAM
# ==========================================================

def main() -> None:
    """Run the complete WA Intelligence update process."""

    print(
        "=" * 60
    )
    print(
        "WA Intelligence briefing generator - Version 2.0 — intelligence scoring"
    )
    print(
        "=" * 60
    )

    raw_stories = collect_news_stories()

    if not raw_stories:
        raise RuntimeError(
            "No stories were collected. Check your internet "
            "connection and try again."
        )

    ranked_stories = classify_and_rank_stories(
        raw_stories
    )

    selected_stories = select_balanced_stories(
        ranked_stories,
        limit=NUMBER_OF_STORIES,
    )

    if not selected_stories:
        raise RuntimeError(
            "Stories were collected, but none passed the "
            "freshness, relevance and quality checks."
        )

    print_selected_story_report(
        selected_stories
    )

    briefing = build_briefing(
        selected_stories
    )

    write_json_safely(
        OUTPUT_FILE,
        briefing,
    )

    print()
    print(
        f"Briefing saved to: {OUTPUT_FILE}"
    )
    print(
        f"Stories selected: "
        f"{briefing['statistics']['story_count']}"
    )
    print(
        f"Sources represented: "
        f"{briefing['statistics']['source_count']}"
    )
    print(
        f"Countries represented: "
        f"{briefing['statistics']['country_count']}"
    )
    print(
        "=" * 60
    )


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print(
            "\nUpdate cancelled by user."
        )

    except Exception as error:
        print(
            f"\nUpdate failed: {error}"
        )

        raise
