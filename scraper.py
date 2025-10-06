#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRF2019 Conference Web Scraper

Author: Ming Liu
Date: September 30, 2025
Description: A comprehensive web scraper for SRF2019 conference papers and abstracts.
             Extracts paper information organized by sessions, downloads PDFs, and exports
             data in multiple formats (JSON, CSV, TXT).

Website: https://proceedings.jacow.org/srf2019/
Features:
- Session-based paper extraction
- PDF download with validation
- Multi-format data export
- Robust error handling and retry mechanisms
- Comprehensive logging
"""

import requests
from bs4 import BeautifulSoup
import os
import json
import time
import re
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any, Optional
import logging
from pathlib import Path

class SRF2019Scraper:
    """
    Web scraper for SRF2019 conference proceedings.
    
    This scraper extracts paper information from the SRF2019 conference website,
    organizing data by sessions and downloading available PDF files.
    """
    
    def __init__(self, base_url: str = "https://proceedings.jacow.org/srf2019/", output_dir: str = "SRF2019_Data"):
        """
        Initialize the SRF2019 scraper.
        
        Args:
            base_url: Base URL of the SRF2019 conference website
            output_dir: Directory to store scraped data and PDFs
        """
        self.base_url = base_url
        self.output_dir = Path(output_dir)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('srf2019_scraper.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # SRF2019 session configuration - will be populated dynamically
        self.sessions_config = []
        
        # Initialize directories and statistics
        self.create_directories()
        self.stats = {'total_papers': 0, 'downloaded_presentations': 0, 'downloaded_papers': 0, 'downloaded_posters': 0, 'errors': 0, 'sessions_processed': 0}
        
        # Load sessions dynamically
        self.load_sessions()
    
    def load_sessions(self):
        """Load session configuration from the SRF2019 website."""
        try:
            r = requests.get('https://proceedings.jacow.org/srf2019/html/sessi0n1.htm')
            soup = BeautifulSoup(r.text, 'html.parser')

            sessions = []

            # Find the session table
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        session_id = cols[0].get_text().strip()
                        session_name = cols[1].get_text().strip()

                        if session_id and session_name and session_id.isupper():
                            sessions.append({
                                'id': session_id,
                                'name': f"{session_id} - {session_name}",
                                'url': f"https://proceedings.jacow.org/srf2019/html/{session_id.lower()}.htm"
                            })

            # Fallback: if no table found, try the old text parsing method
            if not sessions:
                page_text = soup.get_text()
                lines = [line.strip() for line in page_text.split('\n') if line.strip()]

                i = 0
                while i < len(lines):
                    if len(lines[i]) == 5 and lines[i].isupper():  # Session ID like MOFAA
                        session_id = lines[i]
                        if i + 1 < len(lines):
                            session_name = lines[i + 1]
                            sessions.append({
                                'id': session_id,
                                'name': f"{session_id} - {session_name}",
                                'url': f"https://proceedings.jacow.org/srf2019/html/{session_id.lower()}.htm"
                            })
                        i += 2
                    else:
                        i += 1

            self.sessions_config = sessions
            self.logger.info(f"Loaded {len(sessions)} sessions from SRF2019 website")

        except Exception as e:
            self.logger.error(f"Failed to load sessions: {e}")
            self.sessions_config = []
    
    def create_directories(self):
        """Create necessary directory structure for output files."""
        self.output_dir.mkdir(exist_ok=True)
        (self.output_dir / "Presentations").mkdir(exist_ok=True)
        (self.output_dir / "Papers").mkdir(exist_ok=True)
        (self.output_dir / "Posters").mkdir(exist_ok=True)
        (self.output_dir / "Sessions").mkdir(exist_ok=True)
        (self.output_dir / "Debug").mkdir(exist_ok=True)
        self.logger.info(f"Created output directory: {self.output_dir}")
    
    def safe_filename(self, filename: str, max_length: int = 60) -> str:
        """
        Convert filename to safe filesystem name.
        
        Args:
            filename: Original filename
            max_length: Maximum allowed filename length
            
        Returns:
            Safe filename string
        """
        if not filename:
            return "unknown"
        
        # Remove invalid characters
        filename = re.sub(r'[<>:"/\\|?*\r\n]', '_', filename)
        filename = re.sub(r'\s+', ' ', filename)
        filename = filename.strip(' ._')
        
        # Truncate if too long (be more aggressive)
        if len(filename) > max_length:
            # Keep the paper ID part and truncate the title part more aggressively
            parts = filename.split(' - ', 1)
            if len(parts) == 2:
                paper_id_part = parts[0]
                title_part = parts[1]
                # Reserve space for paper ID and minimal title
                title_max = max_length - len(paper_id_part) - 3  # 3 for " - "
                if title_max > 5:  # Only keep minimal title
                    title_part = title_part[:title_max].rsplit(' ', 1)[0] if ' ' in title_part[:title_max] else title_part[:title_max]
                    filename = f"{paper_id_part} - {title_part}"
                else:
                    filename = paper_id_part
            else:
                filename = filename[:max_length].rsplit(' ', 1)[0]
        
        return filename or "unknown"
    
    def get_page_content(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """
        Get webpage content with retry mechanism.
        
        Args:
            url: URL to fetch
            retries: Number of retry attempts
            
        Returns:
            BeautifulSoup object or None if failed
        """
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            except requests.RequestException as e:
                self.logger.warning(f"Failed to fetch page (attempt {attempt + 1}/{retries}) {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    self.logger.error(f"Final failure fetching page {url}: {e}")
                    self.stats['errors'] += 1
        return None
    
    def extract_papers_from_session(self, soup: BeautifulSoup, session_id: str) -> List[Dict[str, Any]]:
        """
        Extract paper information from a session page.

        Args:
            soup: BeautifulSoup object of the session page
            session_id: Session ID (e.g., 'MOFAA')

        Returns:
            List of paper dictionaries
        """
        papers = []
        page_text = soup.get_text()

        # Save debug information
        debug_file = self.output_dir / "Debug" / f"{session_id}_page_text.txt"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_text)

        # Find all paper sections in the HTML
        # Papers are identified by their IDs (like MOFAA1, MOFAA2, etc.)
        paper_pattern = rf'{re.escape(session_id)}(\d+)'
        paper_matches = re.findall(paper_pattern, page_text)

        if not paper_matches:
            self.logger.warning(f"No papers found in session {session_id}")
            return papers

        # Remove duplicates and sort
        paper_nums = sorted(list(set(paper_matches)))
        self.logger.info(f"Found {len(paper_nums)} potential papers in session {session_id}")

        for paper_num in paper_nums:
            paper_id = f"{session_id}{paper_num}"

            # Extract paper details
            paper_info = self.extract_paper_details_from_page(soup, paper_id)
            if paper_info:
                papers.append(paper_info)
                self.logger.info(f"  ✓ {paper_id}: {paper_info['title'][:50]}...")

        return papers
    
    def extract_paper_details_from_page(self, soup: BeautifulSoup, paper_id: str) -> Dict[str, Any]:
        """
        Extract detailed information for a single paper from the session page.

        Args:
            soup: BeautifulSoup object of the session page
            paper_id: Paper ID (e.g., 'MOFAA1')

        Returns:
            Dictionary containing paper information
        """
        paper_info = {
            'paper_id': paper_id,
            'title': '',
            'authors': [],
            'institutions': [],
            'abstract': '',
            'presentation_url': f"https://proceedings.jacow.org/srf2019/talks/{paper_id.lower()}_talk.pdf",
            'paper_url': f"https://proceedings.jacow.org/srf2019/papers/{paper_id.lower()}.pdf",
            'poster_url': f"https://proceedings.jacow.org/srf2019/posters/{paper_id.lower()}_poster.pdf",
            'doi': f"https://doi.org/10.18429/JACoW-SRF2019-{paper_id}",
            'page_number': '',
            'presentation_available': False,
            'paper_available': False,
            'poster_available': False
        }

        # Convert soup to text for easier parsing
        page_text = soup.get_text()

        # Find the paper section by looking for the paper ID
        paper_id_pattern = rf'{re.escape(paper_id)}\s*(\d*)'
        paper_match = re.search(paper_id_pattern, page_text)

        if not paper_match:
            self.logger.warning(f"Could not find paper section for {paper_id}")
            return paper_info

        # Extract text from the match position onwards
        start_pos = paper_match.end()
        remaining_text = page_text[start_pos:]

        # Find the next paper or end of content
        # Look for next paper ID pattern
        next_paper_pattern = r'[A-Z]{5}\d+'
        next_match = re.search(next_paper_pattern, remaining_text)

        if next_match:
            paper_content = remaining_text[:next_match.start()]
        else:
            # Look for common end markers
            end_markers = ['DOI:', 'Received:', 'Accepted:', 'Paper:', 'Cite:', 'Export:']
            min_end = len(remaining_text)
            for marker in end_markers:
                marker_pos = remaining_text.find(marker)
                if marker_pos != -1 and marker_pos < min_end:
                    min_end = marker_pos
            paper_content = remaining_text[:min_end] if min_end < len(remaining_text) else remaining_text

        # Parse the paper content
        lines = [line.strip() for line in paper_content.split('\n') if line.strip()]

        # Extract title (usually the first line after paper ID)
        if lines:
            paper_info['title'] = lines[0]

        # Extract page number (look for pattern like "1" or "9")
        page_pattern = r'\b(\d{1,3})\b'
        for line in lines:
            if re.match(r'^\d{1,3}$', line):
                paper_info['page_number'] = line
                break

        # Extract authors and institutions
        author_lines = []
        institution_lines = []
        abstract_lines = []

        in_abstract = False

        for line in lines:
            # Skip title and page number
            if line == paper_info['title'] or line == paper_info['page_number']:
                continue

            # Check for author lines (contain commas and names)
            if ',' in line and len(line.split(',')) > 1 and not any(keyword in line.lower() for keyword in ['funding', 'doi', 'received', 'accepted']):
                author_lines.append(line)
            # Check for institution lines (contain institution keywords)
            elif any(keyword in line for keyword in ['University', 'Laboratory', 'Institute', 'Center', 'Corporation',
                                                   'School', 'Facility', 'National', 'Synchrotron', 'KEK', 'FRIB', 'LBNL',
                                                   'DESY', 'SLAC', 'CERN', 'Jefferson Lab', 'Argonne']):
                institution_lines.append(line)
            # Abstract content (longer lines that are not authors or institutions)
            elif len(line) > 20 and not line.startswith(('Funding:', 'DOI:', 'Received:', 'Accepted:')):
                abstract_lines.append(line)

        # Process authors
        if author_lines:
            all_authors = []
            for author_line in author_lines:
                # Split by comma and clean up
                authors = [a.strip() for a in author_line.split(',') if a.strip()]
                all_authors.extend(authors)
            paper_info['authors'] = all_authors

        # Process institutions
        if institution_lines:
            paper_info['institutions'] = institution_lines

        # Process abstract
        if abstract_lines:
            paper_info['abstract'] = ' '.join(abstract_lines)

        # Check availability of different file types
        paper_info['presentation_available'] = self.check_pdf_exists(paper_info['presentation_url'])
        paper_info['paper_available'] = self.check_pdf_exists(paper_info['paper_url'])
        paper_info['poster_available'] = self.check_pdf_exists(paper_info['poster_url'])

        return paper_info
    
    def check_pdf_exists(self, pdf_url: str) -> bool:
        """
        Check if PDF file exists and is accessible.
        
        Args:
            pdf_url: URL of the PDF file
            
        Returns:
            True if PDF exists and is accessible
        """
        try:
            response = self.session.head(pdf_url, timeout=10)
            return response.status_code == 200 and 'pdf' in response.headers.get('content-type', '').lower()
        except:
            return False
    
    def scrape_session(self, session: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Scrape all papers from a single session.
        
        Args:
            session: Session configuration dictionary
            
        Returns:
            List of paper dictionaries
        """
        self.logger.info(f"Scraping session: {session['name']}")
        
        soup = self.get_page_content(session['url'])
        if not soup:
            return []
        
        papers = self.extract_papers_from_session(soup, session['id'])
        
        self.stats['total_papers'] += len(papers)
        self.stats['sessions_processed'] += 1
        
        self.logger.info(f"Session {session['id']} results: {len(papers)} papers")
        
        # Display found papers
        for i, paper in enumerate(papers):
            pres_status = "✓" if paper['presentation_available'] else "✗"
            paper_status = "✓" if paper['paper_available'] else "✗"
            poster_status = "✓" if paper['poster_available'] else "✗"
            self.logger.info(f"  {i+1}. {paper['paper_id']}: {paper['title'][:50]}... [P:{pres_status} R:{paper_status} T:{poster_status}]")
        
        return papers
    
    def download_single_file(self, file_url: str, paper_info: Dict[str, Any], session_name: str, folder: str, file_type: str) -> bool:
        """
        Download a single file (presentation, paper, or poster).
        
        Args:
            file_url: URL of the file
            paper_info: Paper information dictionary
            session_name: Name of the session
            folder: Target folder name
            file_type: Type of file (presentation, paper, poster)
            
        Returns:
            True if download successful
        """
        try:
            session_dir = self.output_dir / folder / self.safe_filename(session_name)
            session_dir.mkdir(exist_ok=True, parents=True)
            
            suffix = "_talk" if file_type == "presentation" else ("_poster" if file_type == "poster" else "")
            filename = f"{paper_info['paper_id']}{suffix} - {paper_info['title']}"
            safe_name = self.safe_filename(filename)
            if not safe_name.endswith('.pdf'):
                safe_name += '.pdf'
            
            filepath = session_dir / safe_name
            
            if filepath.exists():
                self.logger.info(f"{file_type.title()} already exists, skipping: {safe_name}")
                return True
            
            response = self.session.get(file_url, stream=True, timeout=60)
            response.raise_for_status()
            
            content_length = int(response.headers.get('content-length', 0))
            if content_length > 0 and content_length < 100:  # Skip obviously wrong small files
                self.logger.warning(f"{file_type.title()} file too small ({content_length} bytes), skipping: {paper_info['paper_id']}")
                return False
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"✅ Downloaded {file_type}: {safe_name} ({content_length} bytes)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to download {file_type} {file_url}: {e}")
            self.stats['errors'] += 1
            return False
    
    def download_files(self, paper_info: Dict[str, Any], session_name: str):
        """
        Download all available files (presentation, paper, poster) for a paper.
        
        Args:
            paper_info: Paper information dictionary
            session_name: Name of the session
        """
        file_types = [
            ('presentation', paper_info['presentation_url'], paper_info['presentation_available'], 'Presentations'),
            ('paper', paper_info['paper_url'], paper_info['paper_available'], 'Papers'),
            ('poster', paper_info['poster_url'], paper_info['poster_available'], 'Posters')
        ]
        
        for file_type, url, available, folder in file_types:
            if available:
                success = self.download_single_file(url, paper_info, session_name, folder, file_type)
                if success:
                    self.stats[f'downloaded_{file_type}s'] += 1
    
    def save_session_data(self, session: Dict[str, str], papers: List[Dict[str, Any]]):
        """
        Save session data to files in multiple formats.
        
        Args:
            session: Session configuration dictionary
            papers: List of paper dictionaries
        """
        session_dir = self.output_dir / "Sessions" / self.safe_filename(session['name'])
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # JSON format
        json_file = session_dir / "papers_data.json"
        session_data = {
            'session_info': session,
            'papers': papers,
            'paper_count': len(papers),
            'scrape_time': time.strftime('%Y-%m-%d %H:%M:%S')
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        # CSV format
        self.save_session_csv(session_dir, papers, session)
        
        # Text format
        self.save_session_txt(session_dir, session, papers)
        
        self.logger.info(f"Saved session data: {session['name']} ({len(papers)} papers)")
    
    def save_session_csv(self, session_dir: Path, papers: List[Dict[str, Any]], session: Dict[str, str]):
        """Save session data in CSV format."""
        import csv
        
        csv_file = session_dir / "papers_data.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            if not papers:
                return
                
            fieldnames = ['session_name', 'paper_id', 'title', 'authors', 'institutions', 'abstract', 
                         'presentation_url', 'presentation_available', 'paper_url', 'paper_available', 
                         'poster_url', 'poster_available', 'doi', 'page_number']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for paper in papers:
                row = {
                    'session_name': session['name'],
                    **paper
                }
                row['authors'] = '; '.join(paper['authors'])
                row['institutions'] = '; '.join(paper['institutions'])
                writer.writerow(row)
    
    def save_session_txt(self, session_dir: Path, session: Dict[str, str], papers: List[Dict[str, Any]]):
        """Save session data in text format."""
        txt_file = session_dir / "papers_summary.txt"
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"Session: {session['name']}\n")
            f.write(f"Session ID: {session['id']}\n")
            f.write(f"URL: {session['url']}\n")
            f.write(f"Scrape time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Paper count: {len(papers)}\n")
            available_presentations = sum(1 for p in papers if p.get('presentation_available', False))
            available_papers_count = sum(1 for p in papers if p.get('paper_available', False))
            available_posters = sum(1 for p in papers if p.get('poster_available', False))
            f.write(f"Available presentations: {available_presentations}/{len(papers)}\n")
            f.write(f"Available papers: {available_papers_count}/{len(papers)}\n")
            f.write(f"Available posters: {available_posters}/{len(papers)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, paper in enumerate(papers, 1):
                pres_status = "✓ Available" if paper.get('presentation_available', False) else "✗ Not available"
                paper_status = "✓ Available" if paper.get('paper_available', False) else "✗ Not available"
                poster_status = "✓ Available" if paper.get('poster_available', False) else "✗ Not available"
                f.write(f"{i}. Paper ID: {paper['paper_id']}\n")
                f.write(f"   Title: {paper['title']}\n")
                if paper['authors']:
                    f.write(f"   Authors: {', '.join(paper['authors'])}\n")
                if paper['institutions']:
                    f.write(f"   Institutions: {'; '.join(paper['institutions'])}\n")
                f.write(f"   Page: {paper.get('page_number', 'N/A')}\n")
                f.write(f"   Presentation Status: {pres_status}\n")
                f.write(f"   Paper Status: {paper_status}\n")
                f.write(f"   Poster Status: {poster_status}\n")
                f.write(f"   Presentation URL: {paper['presentation_url']}\n")
                f.write(f"   Paper URL: {paper['paper_url']}\n")
                f.write(f"   Poster URL: {paper['poster_url']}\n")
                if paper['doi']:
                    f.write(f"   DOI: {paper['doi']}\n")
                if paper['abstract']:
                    abstract_preview = paper['abstract'][:300] + '...' if len(paper['abstract']) > 300 else paper['abstract']
                    f.write(f"   Abstract: {abstract_preview}\n")
                f.write("-" * 60 + "\n")
    
    def create_final_summary(self, all_sessions_data: List[Dict]):
        """
        Create final summary report of all scraped data.
        
        Args:
            all_sessions_data: List of all session data dictionaries
        """
        # Calculate statistics
        total_presentations = sum(
            sum(1 for paper in session_data['papers'] if paper.get('presentation_available', False))
            for session_data in all_sessions_data
        )
        total_papers = sum(
            sum(1 for paper in session_data['papers'] if paper.get('paper_available', False))
            for session_data in all_sessions_data
        )
        total_posters = sum(
            sum(1 for paper in session_data['papers'] if paper.get('poster_available', False))
            for session_data in all_sessions_data
        )
        
        # Text summary
        summary_file = self.output_dir / "SRF2019_Final_Report.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("SRF2019 Conference Complete Scraping Report\n")
            f.write("=" * 60 + "\n")
            f.write(f"Scrape completion time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Sessions processed: {self.stats['sessions_processed']}\n")
            f.write(f"Total papers: {self.stats['total_papers']}\n")
            f.write(f"Available presentations: {total_presentations}\n")
            f.write(f"Available papers: {total_papers}\n")
            f.write(f"Available posters: {total_posters}\n")
            f.write(f"Successfully downloaded presentations: {self.stats['downloaded_presentations']}\n")
            f.write(f"Successfully downloaded papers: {self.stats['downloaded_papers']}\n")
            f.write(f"Successfully downloaded posters: {self.stats['downloaded_posters']}\n")
            f.write(f"Errors: {self.stats['errors']}\n\n")
            
            f.write("Session detailed statistics:\n")
            f.write("-" * 50 + "\n")
            for session_data in all_sessions_data:
                session = session_data['session_info']
                papers = session_data['papers']
                available_presentations = sum(1 for p in papers if p.get('presentation_available', False))
                available_papers_count = sum(1 for p in papers if p.get('paper_available', False))
                available_posters = sum(1 for p in papers if p.get('poster_available', False))
                
                f.write(f"Session: {session['name']}\n")
                f.write(f"   Papers: {len(papers)}\n")
                f.write(f"   Available presentations: {available_presentations}\n")
                f.write(f"   Available papers: {available_papers_count}\n")
                f.write(f"   Available posters: {available_posters}\n")
                f.write(f"   URL: {session['url']}\n")
                
                if papers:
                    f.write("   Paper list:\n")
                    for paper in papers:
                        pdf_icon = "PDF" if paper.get('pdf_available', False) else "---"
                        f.write(f"     [{pdf_icon}] {paper['paper_id']}: {paper['title'][:60]}...\n")
                f.write("\n")
        
        # JSON index
        master_json = self.output_dir / "SRF2019_Complete_Index.json"
        with open(master_json, 'w', encoding='utf-8') as f:
            json.dump({
                'scrape_info': {
                    'scrape_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'sessions_processed': self.stats['sessions_processed'],
                    'total_papers': self.stats['total_papers'],
                    'available_presentations': total_presentations,
                    'available_papers': total_papers,
                    'available_posters': total_posters,
                    'downloaded_presentations': self.stats['downloaded_presentations'],
                    'downloaded_papers': self.stats['downloaded_papers'],
                    'downloaded_posters': self.stats['downloaded_posters'],
                    'errors': self.stats['errors']
                },
                'sessions': all_sessions_data
            }, f, ensure_ascii=False, indent=2)
        
        # Create master CSV
        self.create_master_csv(all_sessions_data)
    
    def create_master_csv(self, all_sessions_data: List[Dict]):
        """Create master CSV file containing all papers."""
        import csv
        
        csv_file = self.output_dir / "SRF2019_All_Papers.csv"
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            fieldnames = ['session_name', 'session_id', 'paper_id', 'title', 'authors', 'institutions', 
                         'abstract', 'presentation_url', 'presentation_available', 'paper_url', 'paper_available',
                         'poster_url', 'poster_available', 'doi', 'page_number']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for session_data in all_sessions_data:
                session_info = session_data['session_info']
                for paper in session_data['papers']:
                    row = {
                        'session_name': session_info['name'],
                        'session_id': session_info['id'],
                        **paper
                    }
                    row['authors'] = '; '.join(paper['authors'])
                    row['institutions'] = '; '.join(paper['institutions'])
                    writer.writerow(row)
    
    def run(self, test_mode: bool = False):
        """
        Run the main scraping process.
        
        Args:
            test_mode: If True, only process first 3 sessions for testing
            
        Returns:
            List of all session data
        """
        self.logger.info("Starting SRF2019 conference data scraping")
        start_time = time.time()
        
        try:
            sessions = self.sessions_config
            
            self.logger.info(f"Prepared to process {len(sessions)} sessions")
            
            if test_mode:
                sessions = sessions[:3]  # Test with first 3 sessions
                self.logger.info(f"Test mode: processing first 3 sessions")
            
            all_sessions_data = []
            
            # Process each session
            for i, session in enumerate(sessions, 1):
                self.logger.info(f"\nProcessing session {i}/{len(sessions)}: {session['name']}")
                
                try:
                    papers = self.scrape_session(session)
                    
                    if papers:
                        self.save_session_data(session, papers)
                        
                        # Download files for all papers in this session
                        for paper in papers:
                            self.download_files(paper, session['name'])
                            time.sleep(1)  # Avoid too frequent requests
                        
                        self.logger.info(f"✅ Session completed: {len(papers)} papers")
                        self.logger.info(f"   Presentations downloaded: {self.stats['downloaded_presentations']}")
                        self.logger.info(f"   Papers downloaded: {self.stats['downloaded_papers']}")
                        self.logger.info(f"   Posters downloaded: {self.stats['downloaded_posters']}")
                    else:
                        self.logger.info(f"⚠️ Session {session['id']} found no papers")
                    
                    all_sessions_data.append({
                        'session_info': session,
                        'papers': papers,
                        'paper_count': len(papers)
                    })
                    
                    time.sleep(2)  # Rest between sessions
                    
                except Exception as e:
                    self.logger.error(f"❌ Error processing session {session['name']}: {e}")
                    self.stats['errors'] += 1
                    continue
            
            # Create final report
            self.create_final_summary(all_sessions_data)
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"\n🎉 Scraping completed! Time elapsed: {elapsed_time:.2f} seconds")
            self.logger.info(f"📊 Final statistics:")
            self.logger.info(f"  ✅ Sessions processed: {self.stats['sessions_processed']}")
            self.logger.info(f"  📄 Total papers: {self.stats['total_papers']}")
            self.logger.info(f"  � Presentations downloaded: {self.stats['downloaded_presentations']}")
            self.logger.info(f"  📄 Papers downloaded: {self.stats['downloaded_papers']}")
            self.logger.info(f"  📋 Posters downloaded: {self.stats['downloaded_posters']}")
            self.logger.info(f"  ❌ Errors: {self.stats['errors']}")
            
            return all_sessions_data
            
        except Exception as e:
            self.logger.error(f"Critical error during scraping process: {e}")
            raise


def main():
    """Main function to run the SRF2019 scraper."""
    print("SRF2019 Conference Web Scraper")
    print("=" * 60)
    print("Comprehensive scraper for SRF2019 conference papers")
    print("Author: Ming Liu")
    print()
    
    scraper = SRF2019Scraper()
    
    try:
        print("Starting test mode...")
        results = scraper.run(test_mode=True)
        
        print("\n" + "="*60)
        print("Test completed successfully!")
        
        # Ask if user wants to continue with full scraping
        print("\nWould you like to continue with full scraping of all sessions?")
        choice = input("Enter 'y' to continue with full scraping, any other key to exit: ").lower().strip()
        
        if choice == 'y':
            print("\nStarting full scraping...")
            results = scraper.run(test_mode=False)
            
            print("\n" + "="*60)
            print("Full scraping completed successfully!")
            print(f"Output directory: {scraper.output_dir}")
            print("\nMain output files:")
            print("  📊 SRF2019_Final_Report.txt - Complete scraping report")
            print("  📈 SRF2019_All_Papers.csv - All papers Excel table")
            print("  🗂️ SRF2019_Complete_Index.json - Complete data index")
            print("  📁 Sessions/ - Session-categorized detailed data")
            print("  � Presentations/ - Downloaded presentation files")
            print("  📁 Papers/ - Downloaded paper files")
            print("  📁 Posters/ - Downloaded poster files")
            print("  🔍 Debug/ - Debug information and page content")
            print("\n💡 Each session contains JSON, CSV, TXT format data")
        
    except KeyboardInterrupt:
        print("\n⏹️ User interrupted scraping")
    except Exception as e:
        print(f"\n❌ Scraping failed: {e}")


if __name__ == "__main__":
    main()