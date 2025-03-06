# BibTeX to DBLP Converter

A Python tool for automated conversion of BibTeX entries to DBLP format. The tool uses the DBLP API to search for entries and match them with the input BibTeX file. This is particularly useful when you have references from various sources (e.g., arXiv, Google Scholar, conference websites) and want to standardize them using DBLP's detailed up-to-date metadata.

## Features

- Levenshtein distance-based similarity scoring for titles (threshold: 0.7) and authors (threshold: 0.4)
- Support for various author name formats and normalizations
- It handles nested DBLP response structures
- Checkpoint-based saving with resume capability to avoid rate-limiting. It saves the progress after each entry, so it can be resumed from the same point (if using the same log file).
- Rate limiting and exponential backoff for API requests

## Installation

```bash
git clone https://github.com/bilgehanertan/bibtex2dblp.git
cd bibtex2dblp
pip install -r requirements.txt
```

## Usage

```bash
python bibtex2dblp.py input.bib [output.bib] [log.csv]
```

Arguments:
- `input.bib`: Input BibTeX file (required)
- `output.bib`: Output file for DBLP entries (default: 'output.bib')
- `log.csv`: Conversion log file (default: 'log.csv')

## Output

The tool generates:
1. A BibTeX file containing DBLP-formatted entries
2. A CSV log file tracking:
   - Original Key
   - Title
   - Authors
   - DBLP Found
   - DBLP Key
   - DBLP Title

## Requirements

- Python 3.6+
- bibtexparser
- requests
- python-Levenshtein


## Acknowledgments
- DBLP for providing their API