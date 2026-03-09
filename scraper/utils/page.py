from bs4 import BeautifulSoup
import re
from difflib import SequenceMatcher
from datetime import datetime
from zoneinfo import ZoneInfo
from dateutil import parser
from dateutil.relativedelta import relativedelta


def similarity(a, b):
    """Calculate text similarity ratio between two strings."""
    return SequenceMatcher(None, a, b).ratio()


def should_update(last_update, refresh_days=7):
    """Check if content should be updated based on age"""
    if not last_update:
        return True
    age = datetime.now(ZoneInfo("Asia/Kolkata")) - last_update
    return age.days >= refresh_days


def extract_context(
    text,
    regex_pattern,
    before=50,
    after=50,
    similarity_threshold=0.7,
    max_char_distance=500,
):
    """
    Extract context around regex matches with intelligent clustering and deduplication.

    Args:
        text: The full text to search in
        regex_pattern: The regex pattern to match (typically dates)
        before: Number of tokens to include before the match
        after: Number of tokens to include after the match
        similarity_threshold: Threshold for considering contexts as similar
        max_char_distance: Maximum character distance to consider dates as part of the same cluster

    Returns:
        List of dictionaries with match and context information
    """
    # Find all matches of the regex in the text
    matches = list(re.finditer(regex_pattern, text))
    if not matches:
        return []

    # First, cluster matches that are close to each other
    matches.sort(key=lambda x: x.start())

    clusters = []
    current_cluster = [matches[0]]

    for i in range(1, len(matches)):
        # If this match is close to the previous one, add to current cluster
        if matches[i].start() - current_cluster[-1].end() < max_char_distance:
            current_cluster.append(matches[i])
        else:
            # Start a new cluster
            clusters.append(current_cluster)
            current_cluster = [matches[i]]

    # Add the last cluster
    if current_cluster:
        clusters.append(current_cluster)

    # Process each cluster to extract a unified context
    cluster_results = []

    for cluster in clusters:
        # Get the start of the first match and end of the last match
        cluster_start = cluster[0].start()
        cluster_end = cluster[-1].end()

        # Convert to token-based positions for more consistent context extraction
        tokens = text.split()
        token_positions = []
        char_count = 0

        for token in tokens:
            token_positions.append(char_count)
            char_count += len(token) + 1  # +1 for the space

        # Find token indices for cluster boundaries
        token_start = 0
        token_end = 0

        for i, pos in enumerate(token_positions):
            if pos <= cluster_start:
                token_start = i
            if pos <= cluster_end:
                token_end = i

        # Calculate the range for extraction with padding
        extract_start = max(0, token_start - before)
        extract_end = min(len(tokens), token_end + after)

        # Extract the tokens and join them back into a string
        context_tokens = tokens[extract_start:extract_end]
        context_text = " ".join(context_tokens)

        # Get all dates in this cluster
        dates = [match.group() for match in cluster]

        # Create a result for this cluster
        cluster_results.append(
            {
                "match": dates[0],  # Primary date (first one)
                "all_dates": dates,  # All dates in the cluster
                "context": context_text,
                "start_token": extract_start,
                "end_token": extract_end,
            }
        )

    # Now perform semantic deduplication on the cluster results
    deduplicated_results = []

    for result in cluster_results:
        # Check if this result is semantically similar to any existing one
        is_duplicate = False

        for existing in deduplicated_results:
            if (
                similarity(result["context"], existing["context"])
                > similarity_threshold
            ):
                # This is a duplicate based on context similarity
                # We can either merge or skip. Here we'll merge dates but keep the most comprehensive context
                existing["all_dates"] = list(
                    set(existing["all_dates"] + result["all_dates"])
                )

                # Keep the most comprehensive context (longer one)
                if len(result["context"]) > len(existing["context"]):
                    existing["context"] = result["context"]

                is_duplicate = True
                break

        if not is_duplicate:
            deduplicated_results.append(result)

    # For compatibility with existing code, create individual entries for each date
    # but avoid duplicating the context
    final_results = []

    for result in deduplicated_results:
        # Create an entry for each unique date in the cluster
        primary_entry = {
            "match": result["match"],
            "context": result["context"],
            "start_token": result["start_token"],
            "end_token": result["end_token"],
            "related_dates": result["all_dates"],
        }
        final_results.append(primary_entry)

    # Filter results based on date recency (keep only if not older than 1 month)
    current_time = datetime.now(ZoneInfo("Asia/Kolkata"))
    cutoff_date = current_time - relativedelta(months=1)
    recent_results = []

    for result in final_results:
        try:
            # Parse the date string
            # Using dayfirst=True as it's common in the target region
            parsed_date = parser.parse(result["match"], dayfirst=True, fuzzy=True)

            # Make timezone aware if it's naive
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=ZoneInfo("Asia/Kolkata"))

            # Keep if the date is not older than 1 month (i.e., >= cutoff)
            if parsed_date >= cutoff_date:
                recent_results.append(result)
        except (ValueError, TypeError, OverflowError):
            # If parsing fails, keep the result to be safe
            recent_results.append(result)

    return recent_results


def clean_body_content(body_content):
    """Clean HTML content by removing scripts, styles, and normalizing whitespace."""
    soup = BeautifulSoup(body_content, "html.parser")

    for script_or_style in soup(["script", "style", "a", "iframe"]):
        script_or_style.extract()

    # Get text or further process the content
    cleaned_content = soup.get_text(separator="\n")
    cleaned_content = "\n".join(
        line.strip() for line in cleaned_content.splitlines() if line.strip()
    )

    return cleaned_content


def extract_semantic_sections(text):
    """Extract semantic sections (paragraphs) from text."""
    # Split text into paragraphs using blank lines as separators
    paragraphs = re.split(r"\n\s*\n", text)

    # Filter out empty paragraphs and clean whitespace
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    return paragraphs
