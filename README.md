# SRF2019 Conference Web Scraper

**Author: Ming Liu**

## Overview
This web scraper is designed to extract all abstracts and papers from the SRF2019 conference (https://proceedings.jacow.org/srf2019/html/sessi0n.htm). The scraper creates folders organized by Session categories and downloads paper information and multiple file types (presentations, papers, posters) for each session.

## File Description
- `scraper.py` - Main scraper script with comprehensive features
- `analyze_results.py` - Results analysis and summary generator
- `requirements.txt` - Python dependencies list
- `README.md` - This documentation
- `index.html` - Project homepage with statistics and links
- `data-explorer.html` - Interactive web interface for browsing papers

## Requirements
- Python 3.7+
- Stable internet connection

## Installation

1. Ensure Python 3.7 or higher is installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Run the main scraper
```bash
python scraper.py
```

### Analyze results
```bash
python analyze_results.py
```

## Output Directory Structure

```
SRF2019_Data/
├── Sessions/                    # Session-categorized paper data
│   ├── THTUT - Thursday Tutorials/
│   │   ├── papers_data.json     # Detailed JSON data
│   │   ├── papers_data.csv      # CSV data (Excel compatible)
│   │   └── papers_summary.txt   # Human-readable text summary
│   ├── SUSPB - Student Poster/
│   └── ...
├── Presentations/               # Presentation files organized by session
│   ├── THTUT - Thursday Tutorials/
│   │   ├── THTUT01_talk - Title.pdf
│   │   └── ...
├── Papers/                      # Paper files organized by session
│   ├── SUSPB - Student Poster/
│   │   ├── SUSPB001 - Title.pdf
│   │   └── ...
├── Posters/                     # Poster files organized by session
│   ├── SUSPB - Student Poster/
│   │   ├── SUSPB001_poster - Title.pdf
│   │   └── ...
├── SRF2019_Complete_Index.json  # Master data index (JSON format)
├── SRF2019_All_Papers.csv      # Complete papers CSV table
├── SRF2019_Final_Report.txt    # Final scraping report
└── Debug/                      # Debug information and logs
```

## Features

### Data Extraction
- Paper IDs and titles
- Author information
- Institution details
- Paper abstracts
- Multiple file types: Presentations, Papers, Posters
- PDF availability checking
- DOI information
- Page numbers

### File Organization
- Automatic session-based folder creation
- Three separate folders for different file types
- PDF files renamed with paper titles and type suffixes
- Multiple output formats (JSON, CSV, TXT)

### Error Handling
- Network request retry mechanism
- Comprehensive logging
- Statistics tracking for each file type

## Configuration Options

You can modify the following configurations in the script:

```python
# Base URL
base_url = "https://proceedings.jacow.org/srf2019/"

# Output directory
output_dir = "SRF2019_Data"

# Request delay (seconds)
delay_between_requests = 1-2

# Retry attempts
max_retries = 3
```

## Log Files
- `srf2019_scraper.log` - Main scraper log

## Web Interface

The project includes two web interfaces:

1. **index.html** - Project homepage with statistics and download links
2. **data-explorer.html** - Interactive browser for papers with search and filtering

## Important Notes

1. **Network Stability**: Ensure stable internet connection, scraping process may take considerable time
2. **Storage Space**: Ensure sufficient disk space for PDF files (potentially hundreds of MB)
3. **Request Frequency**: Script includes appropriate delays to avoid server overload
4. **Filename Restrictions**: PDF filenames are automatically sanitized for compatibility

## FAQ

### Q: What if the scraping process is interrupted?
A: Re-run the script. Already downloaded files will be skipped, only new content will be downloaded.

### Q: Some PDF downloads fail?
A: Check the log files for detailed error information. Could be network issues or missing files.

### Q: How to scrape only specific sessions?
A: Modify the sessions_config list in the script to include only desired sessions.

### Q: Output data format doesn't meet requirements?
A: Modify the save functions to customize output formats.

## Technical Support

If you encounter issues, please check:
1. Python version meets requirements
2. All dependencies are correctly installed
3. Network connection is stable
4. Target website is accessible

## Disclaimer

This script is for academic research purposes only. Please comply with relevant website terms of use and copyright regulations. Users are responsible for any consequences arising from using this script.

## Version History

### v6.0 (Current)
- SRF2019 conference support
- Three file types: Presentations, Papers, Posters
- Interactive web interface
- Enhanced data organization
- Comprehensive error handling
- Multi-format data export

### v5.0 (Previous)
- SRF2021 conference support
- Three file types: Presentations, Papers, Posters
- Interactive web interface
- Enhanced data organization
- Comprehensive error handling
- Multi-format data export

### v4.0 (Previous)
- SRF2023 conference support
- Three file types: Presentations, Papers, Posters
- Interactive web interface
- Enhanced data organization
- Comprehensive error handling
- Multi-format data export

### v2.0 (Previous)
- Improved HTML parsing algorithms
- More accurate paper information extraction
- Multiple output format support
- Detailed statistics
- Enhanced logging

### v1.0 (Initial)
- Basic scraping functionality
- Session categorization
- PDF downloads
- JSON data output