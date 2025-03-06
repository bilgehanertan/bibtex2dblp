#!/usr/bin/env python3

import argparse
import bibtexparser
import requests
import csv
import time
from typing import Dict, List, Optional, Tuple, Set
import logging
from urllib.parse import quote
from requests.exceptions import RequestException, Timeout, TooManyRedirects
import random
from Levenshtein import ratio, distance
import re
import json
import os


class DBLPSearcher:
    def __init__(
        self, timeout: int = 30, max_retries: int = 3, initial_delay: float = 1.0
    ):
        self.base_url = "https://dblp.org/search/publ/api"
        self.session = requests.Session()
        self.timeout = timeout
        self.max_retries = max_retries
        self.initial_delay = initial_delay

    def _normalize_name(self, name: str) -> str:
        """Normalize author name for comparison."""
        # Handle "Last, First" format first
        if "," in name:
            parts = name.split(",")
            if len(parts) == 2:
                last, first = parts
                name = f"{first.strip()} {last.strip()}"

        # Remove special characters and extra whitespace
        name = re.sub(r"[^\w\s]", "", name.lower())
        name = " ".join(name.split())

        # Handle initials and numbers
        parts = name.split()
        normalized_parts = []
        for part in parts:
            # Skip numbers (like "0003", "0004", etc.)
            if part.isdigit():
                continue
            # Keep single initials
            if len(part) == 1:
                normalized_parts.append(part)
            else:
                normalized_parts.append(part)

        return " ".join(normalized_parts)

    def _compare_authors(self, authors1: List[str], authors2: List[str]) -> float:
        """Compare two lists of authors using Levenshtein distance."""
        if not authors1 or not authors2:
            return 0.0

        # Normalize all names
        norm_authors1 = [self._normalize_name(a) for a in authors1]
        norm_authors2 = [self._normalize_name(a) for a in authors2]

        # Log normalized names for debugging
        logging.debug(f"Normalized authors1: {norm_authors1}")
        logging.debug(f"Normalized authors2: {norm_authors2}")

        # Calculate similarity scores for each pair
        total_similarity = 0.0
        matched_indices = set()

        # For each author in the first list
        for i, a1 in enumerate(norm_authors1):
            best_similarity = 0.0
            best_j = -1

            # Find the best matching author in the second list
            for j, a2 in enumerate(norm_authors2):
                if j in matched_indices:
                    continue

                # Calculate similarity between the two names
                similarity = ratio(a1, a2)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_j = j

            # If we found a good match, add it to the total
            if (
                best_j != -1 and best_similarity > 0.7
            ):  # Threshold for considering a match
                matched_indices.add(best_j)
                total_similarity += best_similarity
                logging.debug(
                    f"Matched '{a1}' with '{norm_authors2[best_j]}' (similarity: {best_similarity:.2f})"
                )

        # Calculate the average similarity
        # Use the length of the shorter list to avoid penalizing for extra authors
        min_len = min(len(norm_authors1), len(norm_authors2))
        if min_len == 0:
            return 0.0

        return total_similarity / min_len

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Remove special characters and extra whitespace
        title = re.sub(r"[^\w\s]", "", title.lower())
        title = " ".join(title.split())
        return title

    def _compare_titles(self, title1: str, title2: str) -> float:
        """Compare two titles using Levenshtein distance."""
        if not title1 or not title2:
            return 0.0

        # Normalize titles
        norm_title1 = self._normalize_title(title1)
        norm_title2 = self._normalize_title(title2)

        # Log normalized titles for debugging
        logging.debug(f"Normalized title1: {norm_title1}")
        logging.debug(f"Normalized title2: {norm_title2}")

        # Calculate similarity using Levenshtein ratio
        similarity = ratio(norm_title1, norm_title2)
        logging.debug(f"Title similarity: {similarity:.2f}")

        return similarity

    def _make_request_with_retry(self, params: Dict) -> Optional[Dict]:
        """Make request with exponential backoff retry logic."""
        delay = self.initial_delay

        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    self.base_url, params=params, timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()

            except Timeout:
                logging.warning(
                    f"Request timed out (attempt {attempt + 1}/{self.max_retries})"
                )
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                    delay += random.uniform(0, 1)  # Add jitter

            except TooManyRedirects:
                logging.error("Too many redirects")
                return None

            except RequestException as e:
                if "429" in str(e):  # Too Many Requests
                    logging.warning(
                        f"Rate limited (attempt {attempt + 1}/{self.max_retries})"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(delay)
                        delay *= 2
                        delay += random.uniform(0, 1)
                else:
                    logging.error(f"Request failed: {e}")
                    return None

        return None

    def search_publication(self, title: str, authors: List[str]) -> Optional[Dict]:
        """Search for a publication in DBLP using title and authors."""
        # Construct query string
        query_parts = [title]
        if authors:
            query_parts.extend(authors[:2])  # Use first two authors
        query = " ".join(query_parts)

        # URL encode the query
        encoded_query = quote(query)

        try:
            # Make request with retry logic
            data = self._make_request_with_retry(
                {
                    "q": query,
                    "format": "json",
                    "h": 5,  # Get more results to check author matches
                }
            )

            if not data:
                return None

            # Log the raw response for debugging
            logging.debug(f"DBLP Response: {json.dumps(data, indent=2)}")

            # Check if we got any hits
            hits = data.get("result", {}).get("hits", {}).get("hit", [])
            if not hits:
                return None

            # Get DBLP info from the first hit
            dblp_info = hits[0].get("info", {})
            dblp_authors = []
            dblp_title = dblp_info.get("title", "")

            # Compare titles first
            title_similarity = self._compare_titles(title, dblp_title)
            if title_similarity < 0.7:  # Threshold for title match
                logging.warning(
                    f"Title similarity too low ({title_similarity:.2f}), rejecting match"
                )
                return None

            # Log the info structure for debugging
            logging.debug(f"DBLP Info: {json.dumps(dblp_info, indent=2)}")

            # Handle different possible author formats in DBLP response
            authors_field = dblp_info.get("authors")
            if authors_field is None:
                logging.warning("No authors field found in DBLP response")
                return None

            # Log the authors field type and content
            logging.debug(f"Authors field type: {type(authors_field)}")
            logging.debug(f"Authors field content: {authors_field}")

            if isinstance(authors_field, str):
                dblp_authors = authors_field.split(" and ")
            elif isinstance(authors_field, list):
                # Handle list of author objects
                dblp_authors = []
                for author in authors_field:
                    if isinstance(author, dict):
                        dblp_authors.append(author.get("text", ""))
                    elif isinstance(author, str):
                        dblp_authors.append(author)
                    elif isinstance(author, list):
                        # Handle nested list of authors
                        for subauthor in author:
                            if isinstance(subauthor, dict):
                                dblp_authors.append(subauthor.get("text", ""))
                            elif isinstance(subauthor, str):
                                dblp_authors.append(subauthor)
                    else:
                        logging.warning(f"Unexpected author type: {type(author)}")
                        continue
            elif isinstance(authors_field, dict):
                # Handle dictionary of author objects
                dblp_authors = []
                for author in authors_field.values():
                    if isinstance(author, dict):
                        dblp_authors.append(author.get("text", ""))
                    elif isinstance(author, str):
                        dblp_authors.append(author)
                    elif isinstance(author, list):
                        # Handle nested list of authors
                        for subauthor in author:
                            if isinstance(subauthor, dict):
                                dblp_authors.append(subauthor.get("text", ""))
                            elif isinstance(subauthor, str):
                                dblp_authors.append(subauthor)
                    else:
                        logging.warning(
                            f"Unexpected author type in dict: {type(author)}"
                        )
                        continue
            else:
                logging.warning(f"Unexpected authors field type: {type(authors_field)}")
                return None

            # Filter out empty author names
            dblp_authors = [a for a in dblp_authors if a.strip()]

            if not dblp_authors:
                logging.warning("No valid authors found in DBLP response")
                return None

            # Compare authors
            author_similarity = self._compare_authors(authors, dblp_authors)

            # Log the comparison
            logging.info(f"Author similarity: {author_similarity:.2f}")
            logging.info(f"Original authors: {authors}")
            logging.info(f"DBLP authors: {dblp_authors}")

            # If author similarity is too low, return None
            if author_similarity < 0.4:  # Threshold for considering a match
                logging.warning("Author similarity too low, rejecting match")
                return None

            return dblp_info

        except Exception as e:
            logging.error(f"Error searching DBLP: {e}")
            logging.error(f"Error type: {type(e)}")
            import traceback

            logging.error(f"Traceback: {traceback.format_exc()}")
            return None


def load_processed_entries(log_file: str) -> Set[str]:
    """Load already processed entries from the log file."""
    processed = set()
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                processed.add(row["Original Key"])
    return processed


def process_bibtex(input_file: str, output_file: str, log_file: str):
    """Process BibTeX file and find DBLP entries."""
    # Initialize DBLP searcher
    searcher = DBLPSearcher()

    # Load already processed entries
    processed_entries = load_processed_entries(log_file)
    logging.info(f"Found {len(processed_entries)} already processed entries")

    # Read input BibTeX file
    with open(input_file, "r", encoding="utf-8") as bibtex_file:
        bib_database = bibtexparser.load(bibtex_file)

    # Prepare output BibTeX entries
    output_entries = []

    # If output file exists, load existing entries
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as bibtex_file:
            existing_db = bibtexparser.load(bibtex_file)
            output_entries = existing_db.entries
            logging.info(
                f"Loaded {len(output_entries)} existing entries from output file"
            )

    # Prepare CSV log
    log_mode = "a" if os.path.exists(log_file) else "w"
    with open(log_file, log_mode, newline="", encoding="utf-8") as csvfile:
        csvwriter = csv.writer(csvfile)
        if log_mode == "w":  # Only write header for new file
            csvwriter.writerow(
                [
                    "Original Key",
                    "Title",
                    "Authors",
                    "DBLP Found",
                    "DBLP Key",
                    "DBLP Title",
                ]
            )

        # Process each entry
        total_entries = len(bib_database.entries)
        processed_count = 0

        for idx, entry in enumerate(bib_database.entries, 1):
            entry_key = entry.get("ID", "")

            # Skip if already processed
            if entry_key in processed_entries:
                logging.info(f"Skipping already processed entry: {entry_key}")
                continue

            logging.info(f"Processing entry {idx}/{total_entries}: {entry_key}")

            # Extract title and authors
            title = entry.get("title", "")

            # Handle author parsing
            authors = []
            if "author" in entry:
                author_str = entry["author"]
                # Replace newlines with spaces
                author_str = author_str.replace("\n", " ")
                # Split by 'and' and clean up
                authors = [a.strip() for a in author_str.split(" and ") if a.strip()]

            # Search DBLP
            dblp_info = searcher.search_publication(title, authors)

            # Log the result
            csvwriter.writerow(
                [
                    entry_key,
                    title,
                    "; ".join(authors),
                    "Yes" if dblp_info else "No",
                    dblp_info.get("key", "") if dblp_info else "",
                    dblp_info.get("title", "") if dblp_info else "",
                ]
            )

            # If DBLP entry found, update the entry
            if dblp_info:
                # Keep the original key
                entry["ID"] = entry_key

                # Convert DBLP authors to string format
                dblp_authors = dblp_info.get("authors", "")
                if isinstance(dblp_authors, list):
                    # Handle list of author dictionaries with @pid and text fields
                    if dblp_authors and isinstance(dblp_authors[0], dict):
                        dblp_authors = " and ".join(
                            author.get("text", str(author)) for author in dblp_authors
                        )
                    else:
                        dblp_authors = " and ".join(str(a) for a in dblp_authors)
                elif isinstance(dblp_authors, dict):
                    # Handle dictionary of author objects
                    author_texts = []
                    for author in dblp_authors.values():
                        if isinstance(author, dict):
                            author_texts.append(author.get("text", str(author)))
                        elif isinstance(author, str):
                            author_texts.append(author)
                        elif isinstance(author, list):
                            # Handle nested list of authors
                            for subauthor in author:
                                if isinstance(subauthor, dict):
                                    author_texts.append(
                                        subauthor.get("text", str(subauthor))
                                    )
                                elif isinstance(subauthor, str):
                                    author_texts.append(subauthor)
                    dblp_authors = " and ".join(author_texts)
                else:
                    dblp_authors = str(dblp_authors)

                # Log the authors for debugging
                logging.info(f"Original authors: {authors}")
                logging.info(f"DBLP authors: {dblp_authors}")

                # Update other fields with DBLP info
                entry.update(
                    {
                        "title": dblp_info.get("title", entry.get("title", "")),
                        "author": dblp_authors,  # Make sure we save the authors
                        "year": dblp_info.get("year", entry.get("year", "")),
                        "journal": dblp_info.get("venue", entry.get("journal", "")),
                        "booktitle": dblp_info.get("venue", entry.get("booktitle", "")),
                        "volume": dblp_info.get("volume", entry.get("volume", "")),
                        "number": dblp_info.get("number", entry.get("number", "")),
                        "pages": dblp_info.get("pages", entry.get("pages", "")),
                        "url": dblp_info.get("ee", entry.get("url", "")),
                        "doi": dblp_info.get("doi", entry.get("doi", "")),
                        "dblp_key": dblp_info.get("key", ""),
                    }
                )

            # Add to output entries
            output_entries.append(entry)

            # Save checkpoint after each entry
            with open(output_file, "w", encoding="utf-8") as bibtex_file:
                bib_database.entries = output_entries  # Update the entries
                bibtexparser.dump(bib_database, bibtex_file)

            # Add a small delay to avoid overwhelming the API
            time.sleep(0.5)

            # Increment processed count and check if we should prompt
            processed_count += 1
            if processed_count % 15 == 0:
                response = input(
                    f"\nProcessed {processed_count} entries. Continue? (Y/N): "
                )
                if response.lower() != "y":
                    logging.info("User chose to stop processing.")
                    break

    logging.info(
        f"Processing complete. Check {output_file} and {log_file} for results."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Convert BibTeX entries to DBLP format"
    )
    parser.add_argument("input_file", help="Input BibTeX file")
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Output BibTeX file with DBLP entries",
        default="output.bib",
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        help="CSV log file for tracking conversions",
        default="log.csv",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    try:
        process_bibtex(args.input_file, args.output_file, args.log_file)
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
