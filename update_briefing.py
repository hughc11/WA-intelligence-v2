"""
WA Intelligence
Daily briefing generator
Version 1.0

This script:
1. Searches public Google News RSS feeds.
2. Collects recent West Africa stories.
3. Removes duplicates.
4. Categorises and ranks stories.
5. Writes briefing.json for the website.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ==========================================================
# PROJECT SETTINGS
# ==========================================================

PROJECT_FOLDER = Path(__file__).resolve().parent

OUTPUT_FILE = PROJECT_FOLDER / "briefing.json"

NUMBER_OF_STORIES = 10

REQUEST_TIMEOUT_SECONDS = 20

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
    "West Africa politics",
    "West Africa economy",
    "West Africa security",
    "ECOWAS",
    "Nigeria politics economy",
    "Ghana economy politics",
    "Senegal politics economy",
    "Cote d'Ivoire economy",
    "Sahel security",
    "West Africa investment business",
    "West Africa climate agriculture",
]


# ==========================================================
# COUNTRY KEYWORDS
# ==========================================================

COUNTRY_KEYWORDS = {
    "Benin": ["benin"],
    "Burkina Faso": ["burkina faso", "burkinabe"],
    "Cabo Verde": ["cabo verde", "cape verde"],
    "Côte d'Ivoire": [
        "cote d'ivoire",
        "côte d'ivoire",
        "ivory coast",
        "ivorian",
    ],
    "The Gambia": ["the gambia", "gambia", "gambian"],
    "Ghana": ["ghana", "ghanaian"],
    "Guinea": ["guinea", "guinean"],
    "Guinea-Bissau": ["guinea-bissau", "guinea bissau"],
    "Liberia": ["liberia", "liberian"],
    "Mali": ["mali", "malian"],
    "Mauritania": ["mauritania", "mauritanian"],
    "Niger": ["niger", "nigerien"],
    "Nigeria": ["nigeria", "nigerian"],
    "Senegal": ["senegal", "senegalese"],
    "Sierra Leone": ["sierra leone", "sierra leonean"],
    "Togo": ["togo", "togolese"],
}


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
        "militant",
        "insurgent",
        "conflict",
        "violence",
        "coup",
        "border",
        "kidnap",
        "jihadist",
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
    ],
}


# ==========================================================
# BASIC TEXT HELPERS
# ==========================================================

def clean_text(value: str | None) -> str:
    """
    Remove HTML, repeated whitespace and encoded characters.
    """

    if not value:
        return ""

    value = html.unescape(value)

    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def normalise_text(value: str) -> str:
    """
    Create a simplified version of text for matching and
    duplicate detection.
    """

    value = clean_text(value).lower()

    value = re.sub(
        r"[^a-z0-9\s]",
        " ",
        value,
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def create_story_id(title: str, url: str) -> str:
    """
    Create a stable identifier for a news story.
    """

    raw_value = f"{normalise_text(title)}|{url}"

    return hashlib.sha256(
        raw_value.encode("utf-8")
    ).hexdigest()[:16]# ==========================================================
# GOOGLE NEWS RSS
# ==========================================================

def build_google_news_url(search_term: str) -> str:
    """
    Build a Google News RSS URL for an English-language search.
    """

    encoded_query = urllib.parse.quote_plus(search_term)

    return (
        "https://news.google.com/rss/search"
        f"?q={encoded_query}"
        "&hl=en-GB"
        "&gl=GB"
        "&ceid=GB:en"
    )


def download_feed(url: str) -> bytes:
    """
    Download one RSS feed and return its raw XML bytes.
    """

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
    """
    Convert an RSS publication date into ISO format where possible.
    """

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

    return value.strip()


def split_google_news_title(
    raw_title: str,
) -> tuple[str, str]:
    """
    Google News titles often end with ' - Publisher'.
    Separate the article title from the publisher name.
    """

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
    """
    Parse one RSS feed into a list of story dictionaries.
    """

    root = ET.fromstring(xml_data)

    stories: list[dict[str, Any]] = []

    for item in root.findall(
        ".//item"
    ):
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
    """
    Download and combine all configured Google News searches.
    A failed feed is skipped rather than stopping the script.
    """

    collected: list[dict[str, Any]] = []

    for search_term in NEWS_SEARCHES:
        feed_url = build_google_news_url(
            search_term
        )

        print(
            f"Collecting: {search_term}"
        )

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

    print(
        f"Collected {len(collected)} raw stories"
    )

    return collected# ==========================================================
# STORY CLASSIFICATION
# ==========================================================

def detect_country(story: dict[str, Any]) -> str:
    """
    Detect the most likely country from a story's title,
    summary and search term.
    """

    searchable_text = normalise_text(
        " ".join(
            [
                story.get("title", ""),
                story.get("summary", ""),
                story.get("search_term", ""),
            ]
        )
    )

    for country_name, keywords in COUNTRY_KEYWORDS.items():
        for keyword in keywords:
            if normalise_text(keyword) in searchable_text:
                return country_name

    return "Regional"


def detect_category(story: dict[str, Any]) -> str:
    """
    Assign the category with the highest keyword score.
    """

    searchable_text = normalise_text(
        " ".join(
            [
                story.get("title", ""),
                story.get("summary", ""),
                story.get("search_term", ""),
            ]
        )
    )

    category_scores: dict[str, int] = {}

    for category_name, keywords in CATEGORY_KEYWORDS.items():
        score = 0

        for keyword in keywords:
            normalised_keyword = normalise_text(keyword)

            if normalised_keyword in searchable_text:
                score += 1

        category_scores[category_name] = score

    best_category = max(
        category_scores,
        key=category_scores.get,
    )

    if category_scores[best_category] == 0:
        return "Politics"

    return best_category


# ==========================================================
# DUPLICATE REMOVAL
# ==========================================================

def title_word_set(title: str) -> set[str]:
    """
    Convert a title into a set of meaningful words.
    """

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
    """
    Compare two titles using word overlap.
    """

    first_words = title_word_set(first_title)
    second_words = title_word_set(second_title)

    if not first_words or not second_words:
        return False

    overlap = len(
        first_words.intersection(second_words)
    )

    smaller_title_size = min(
        len(first_words),
        len(second_words),
    )

    similarity = overlap / smaller_title_size

    return similarity >= 0.65


def remove_duplicate_stories(
    stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Remove repeated URLs and stories with very similar titles.
    """

    unique_stories: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for story in stories:
        url = story.get("url", "").strip()

        if not url or url in seen_urls:
            continue

        duplicate_found = False

        for existing_story in unique_stories:
            if titles_are_similar(
                story.get("title", ""),
                existing_story.get("title", ""),
            ):
                duplicate_found = True
                break

        if duplicate_found:
            continue

        seen_urls.add(url)
        unique_stories.append(story)

    print(
        f"{len(unique_stories)} stories remain after deduplication"
    )

    return unique_stories


# ==========================================================
# STORY RANKING
# ==========================================================

SOURCE_QUALITY_SCORES = {
    "Reuters": 10,
    "Associated Press": 10,
    "AP News": 10,
    "BBC": 9,
    "BBC News": 9,
    "Financial Times": 9,
    "The Guardian": 8,
    "Al Jazeera": 8,
    "Bloomberg": 8,
    "France 24": 8,
    "Africanews": 7,
    "The Africa Report": 7,
    "BusinessDay": 7,
    "Premium Times": 7,
    "Daily Trust": 6,
    "Vanguard": 6,
    "ThisDay": 6,
}


IMPORTANT_TERMS = {
    "election": 5,
    "coup": 6,
    "president": 4,
    "government": 3,
    "ecowas": 5,
    "inflation": 4,
    "debt": 4,
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
    "flood": 3,
    "food security": 4,
}


def publication_timestamp(story: dict[str, Any]) -> float:
    """
    Return a sortable timestamp from published_at.
    """

    value = story.get("published_at", "")

    if not value:
        return 0.0

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return parsed.timestamp()

    except ValueError:
        return 0.0


def source_quality_score(source: str) -> int:
    """
    Score recognised publishers more highly.
    """

    source_lower = source.lower()

    for publisher, score in SOURCE_QUALITY_SCORES.items():
        if publisher.lower() in source_lower:
            return score

    return 3


def story_importance_score(
    story: dict[str, Any],
) -> float:
    """
    Calculate a simple political-risk importance score.
    """

    score = 0.0

    title = normalise_text(
        story.get("title", "")
    )

    summary = normalise_text(
        story.get("summary", "")
    )

    combined_text = f"{title} {summary}"

    score += source_quality_score(
        story.get("source", "")
    )

    for term, term_score in IMPORTANT_TERMS.items():
        if normalise_text(term) in combined_text:
            score += term_score

    if story.get("country") != "Regional":
        score += 2

    category = story.get("category", "")

    if category == "Security":
        score += 3
    elif category == "Politics":
        score += 2
    elif category == "Economy":
        score += 2

    score += publication_timestamp(story) / 10_000_000_000

    return score


def classify_and_rank_stories(
    stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Detect country and category, remove duplicates,
    score stories and return the strongest items first.
    """

    classified: list[dict[str, Any]] = []

    for story in stories:
        enriched_story = dict(story)

        enriched_story["country"] = detect_country(
            enriched_story
        )

        enriched_story["category"] = detect_category(
            enriched_story
        )

        enriched_story["importance_score"] = (
            story_importance_score(enriched_story)
        )

        classified.append(enriched_story)

    unique_stories = remove_duplicate_stories(
        classified
    )

    ranked_stories = sorted(
        unique_stories,
        key=lambda story: (
            story.get("importance_score", 0),
            publication_timestamp(story),
        ),
        reverse=True,
    )

    return ranked_stories# ==========================================================
# SUMMARY CLEANING
# ==========================================================

def shorten_text(
    value: str,
    maximum_length: int = 320,
) -> str:
    """
    Shorten text cleanly without cutting through a word.
    """

    value = clean_text(value)

    if len(value) <= maximum_length:
        return value

    shortened = value[:maximum_length].rsplit(
        " ",
        1,
    )[0]

    return shortened.rstrip(".,;:") + "…"


def create_story_summary(
    story: dict[str, Any],
) -> str:
    """
    Build a concise summary using the RSS description.
    Falls back to the headline where necessary.
    """

    description = clean_text(
        story.get("summary", "")
    )

    title = clean_text(
        story.get("title", "")
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

    return (
        f"This development concerns {title.lower()}."
        if title
        else "No summary is available for this story."
    )


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


def select_balanced_stories(
    ranked_stories: list[dict[str, Any]],
    limit: int = NUMBER_OF_STORIES,
) -> list[dict[str, Any]]:
    """
    Select a varied briefing rather than allowing one category
    or one country to dominate the entire page.
    """

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    category_counts: dict[str, int] = {
        category: 0
        for category in CATEGORY_TARGETS
    }

    country_counts: dict[str, int] = {}

    for category, target in CATEGORY_TARGETS.items():
        for story in ranked_stories:
            if len(selected) >= limit:
                break

            story_id = story.get("id", "")

            if story_id in selected_ids:
                continue

            if story.get("category") != category:
                continue

            story_country = story.get(
                "country",
                "Regional",
            )

            if country_counts.get(
                story_country,
                0,
            ) >= 2:
                continue

            selected.append(story)
            selected_ids.add(story_id)

            category_counts[category] += 1
            country_counts[story_country] = (
                country_counts.get(
                    story_country,
                    0,
                )
                + 1
            )

            if category_counts[category] >= target:
                break

    for story in ranked_stories:
        if len(selected) >= limit:
            break

        story_id = story.get("id", "")

        if story_id in selected_ids:
            continue

        story_country = story.get(
            "country",
            "Regional",
        )

        if country_counts.get(
            story_country,
            0,
        ) >= 3:
            continue

        selected.append(story)
        selected_ids.add(story_id)

        country_counts[story_country] = (
            country_counts.get(
                story_country,
                0,
            )
            + 1
        )

    return selected[:limit]


# ==========================================================
# EXECUTIVE SUMMARY
# ==========================================================

def category_summary(
    stories: list[dict[str, Any]],
) -> str:
    """
    Describe the most prominent categories in the briefing.
    """

    counts: dict[str, int] = {}

    for story in stories:
        category = story.get(
            "category",
            "General",
        )

        counts[category] = (
            counts.get(category, 0) + 1
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
    """
    Generate a concise overview from the selected stories.
    """

    if not stories:
        return (
            "No suitable stories were available for today's "
            "West Africa briefing."
        )

    named_countries = []

    for story in stories:
        country = story.get(
            "country",
            "Regional",
        )

        if (
            country != "Regional"
            and country not in named_countries
        ):
            named_countries.append(country)

    country_text = ", ".join(
        named_countries[:4]
    )

    themes = category_summary(stories)

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
        if story.get("category") == "Security"
    )

    economy_count = sum(
        1
        for story in stories
        if story.get("category") == "Economy"
    )

    closing_parts = []

    if security_count:
        closing_parts.append(
            "Security pressures remain an important source "
            "of political and humanitarian risk"
        )

    if economy_count:
        closing_parts.append(
            "economic policy and market conditions continue "
            "to influence investor confidence and household welfare"
        )

    if closing_parts:
        opening += " " + "; while ".join(
            closing_parts
        ) + "."

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
    """
    Rotate the learning point according to the day of the year.
    """

    day_number = datetime.now(
        timezone.utc
    ).timetuple().tm_yday

    index = day_number % len(
        LEARNING_POINTS
    )

    return LEARNING_POINTS[index]# ==========================================================
# FINAL OUTPUT PREPARATION
# ==========================================================

def prepare_story_for_output(
    story: dict[str, Any],
    rank: int,
) -> dict[str, Any]:
    """
    Convert an internal story dictionary into the structure
    used by the website.
    """

    return {
        "rank": rank,
        "id": story.get("id", ""),
        "title": clean_text(
            story.get("title", "")
        ),
        "summary": create_story_summary(
            story
        ),
        "source": clean_text(
            story.get("source", "Unknown source")
        ),
        "url": story.get("url", ""),
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
            float(
                story.get(
                    "importance_score",
                    0,
                )
            ),
            2,
        ),
    }


def build_briefing(
    selected_stories: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Assemble the complete briefing object for briefing.json.
    """

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
            "searches, classified using keyword rules, filtered for "
            "near-duplicates and ranked using source quality, recency "
            "and political-risk relevance."
        ),
    }


# ==========================================================
# SAFE FILE WRITING
# ==========================================================

def write_json_safely(
    output_path: Path,
    data: dict[str, Any],
) -> None:
    """
    Write JSON to a temporary file before replacing the old file.
    This reduces the risk of leaving a broken briefing.json.
    """

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

        file.write("\n")

    temporary_path.replace(
        output_path
    )


# ==========================================================
# MAIN PROGRAM
# ==========================================================

def main() -> None:
    """
    Run the complete WA Intelligence update process.
    """

    print("=" * 60)
    print("WA Intelligence briefing generator")
    print("=" * 60)

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
            "Stories were collected, but none were suitable "
            "for the final briefing."
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
    print("=" * 60)


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