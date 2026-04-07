# Data Directory

This directory contains the Q&A pair data generated from email history.

**Note**: For privacy reasons, raw data files are not included in the public repository.

## Available Data Files

To request the data files, please contact the repository maintainer.

## Generating Your Own Data

```bash
# 1. Fetch emails from your inbox
python _fetch_allegro_emails.py

# 2. Analyze and extract Q&A pairs
python _analyze_allegro_emails.py

# 3. Generate booking-specific training data
python scripts/stats_report.py
```

After running the scripts, the following files will be generated:
- `qa_pairs.json` — full Q&A pair dataset
- `booking_qa_pairs.json` — booking operations subset
- `booking_training_data.json` — LLM fine-tuning dataset
- `booking_training_raw.txt` — plain text format
- `booking_system_prompt.txt` — system prompt template
