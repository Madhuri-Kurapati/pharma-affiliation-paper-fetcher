import requests
import xml.etree.ElementTree as ET
import json
import csv
import re
import time
from datetime import datetime
from typing import List, Dict, Optional, Set
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ResearchPaperFetcher:
    def __init__(self):
        """Initialize the research paper fetcher with pharmaceutical/biotech company patterns."""
        
        # Comprehensive list of pharmaceutical and biotech companies
        self.pharma_biotech_companies = {
            # Major Pharmaceutical Companies
            'pfizer', 'moderna', 'johnson & johnson', 'j&j', 'roche', 'novartis', 'merck',
            'gsk', 'glaxosmithkline', 'sanofi', 'bayer', 'abbvie', 'bristol myers squibb',
            'bms', 'astrazeneca', 'eli lilly', 'lilly', 'boehringer ingelheim', 'takeda',
            'gilead', 'amgen', 'biogen', 'celgene', 'regeneron', 'vertex', 'alexion',
            
            # Biotech Companies
            'genentech', 'illumina', 'thermo fisher', 'agilent', 'waters', 'bio-rad',
            'qiagen', 'invitrogen', 'applied biosystems', 'becton dickinson', 'bd',
            'danaher', 'medtronic', 'abbott', 'stryker', 'intuitive surgical',
            
            # Vaccine Companies
            'biontech', 'curevac', 'translate bio', 'arcturus', 'novavax',
            
            # Generic keywords
            'pharmaceuticals', 'pharmaceutical', 'biotech', 'biotechnology', 'biopharmaceutical',
            'biopharma', 'life sciences', 'drug discovery', 'therapeutics', 'pharma',
            'medicines', 'clinical research', 'pharmaceutical research', 'drug development',
            'medicinal chemistry', 'pharmaceutical sciences'
        }
        
        # Additional patterns for company identification
        self.company_patterns = [
            r'\b\w+\s+pharmaceuticals?\b',
            r'\b\w+\s+biotech\b',
            r'\b\w+\s+therapeutics?\b',
            r'\b\w+\s+biopharma\b',
            r'\b\w+\s+life\s+sciences?\b',
            r'\b\w+\s+medicines?\b',
            r'\binc\.?\b',
            r'\bcorp\.?\b',
            r'\bltd\.?\b',
            r'\bco\.?\b',
            r'\bcompany\b'
        ]

    def is_pharma_biotech_affiliation(self, affiliation: str) -> bool:
        """Check if an affiliation is related to pharmaceutical or biotech companies."""
        if not affiliation:
            return False
        
        affiliation_lower = affiliation.lower()
        
        # Check direct company name matches
        for company in self.pharma_biotech_companies:
            if company in affiliation_lower:
                return True
        
        # Check patterns
        for pattern in self.company_patterns:
            if re.search(pattern, affiliation_lower):
                # Additional validation to avoid false positives
                if any(keyword in affiliation_lower for keyword in 
                       ['pharma', 'biotech', 'therapeutic', 'medicine', 'drug', 'clinical']):
                    return True
        
        return False

    def fetch_arxiv_papers(self, query: str, max_results: int = 100) -> List[Dict]:
        """Fetch papers from arXiv API."""
        logger.info(f"Fetching papers from arXiv for query: {query}")
        
        url = "http://export.arxiv.org/api/query"
        params = {
            'search_query': query,
            'start': 0,
            'max_results': max_results,
            'sortBy': 'lastUpdatedDate',
            'sortOrder': 'descending'
        }
        
        papers = []
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            entries = root.findall('{http://www.w3.org/2005/Atom}entry')
            
            for entry in entries:
                try:
                    paper = self._parse_arxiv_entry(entry)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    logger.warning(f"Error parsing arXiv entry: {e}")
                    continue
            
            logger.info(f"Successfully fetched {len(papers)} papers from arXiv")
            
        except Exception as e:
            logger.error(f"Error fetching from arXiv: {e}")
        
        return papers

    def _parse_arxiv_entry(self, entry) -> Optional[Dict]:
        """Parse an arXiv entry into a paper dictionary."""
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        try:
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None else "No title"
            
            # Get authors
            authors = []
            author_elements = entry.findall('atom:author', ns)
            for author_elem in author_elements:
                name_elem = author_elem.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text.strip())
            
            # Get abstract
            summary_elem = entry.find('atom:summary', ns)
            abstract = summary_elem.text.strip() if summary_elem is not None else ""
            
            # Get publication date
            published_elem = entry.find('atom:published', ns)
            pub_date = published_elem.text.strip() if published_elem is not None else ""
            
            # Get arXiv ID and URL
            id_elem = entry.find('atom:id', ns)
            arxiv_url = id_elem.text.strip() if id_elem is not None else ""
            arxiv_id = arxiv_url.split('/')[-1] if arxiv_url else ""
            
            # Get categories
            categories = []
            category_elements = entry.findall('atom:category', ns)
            for cat_elem in category_elements:
                term = cat_elem.get('term', '')
                if term:
                    categories.append(term)
            
            return {
                'source': 'arXiv',
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'publication_date': pub_date,
                'url': arxiv_url,
                'id': arxiv_id,
                'categories': categories,
                'affiliations': []  # arXiv doesn't provide detailed affiliations
            }
            
        except Exception as e:
            logger.error(f"Error parsing arXiv entry: {e}")
            return None

    def fetch_pubmed_papers(self, query: str, max_results: int = 100) -> List[Dict]:
        """Fetch papers from PubMed API."""
        logger.info(f"Fetching papers from PubMed for query: {query}")
        
        papers = []
        
        try:
            # First, search for paper IDs
            search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            search_params = {
                'db': 'pubmed',
                'term': query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'most recent'
            }
            
            search_response = requests.get(search_url, params=search_params, timeout=30)
            search_response.raise_for_status()
            search_data = search_response.json()
            
            if 'esearchresult' not in search_data or 'idlist' not in search_data['esearchresult']:
                logger.warning("No PubMed search results found")
                return papers
            
            paper_ids = search_data['esearchresult']['idlist']
            
            if not paper_ids:
                logger.warning("No PubMed paper IDs found")
                return papers
            
            # Fetch detailed information for each paper
            # Process in batches to avoid API limits
            batch_size = 20
            for i in range(0, len(paper_ids), batch_size):
                batch_ids = paper_ids[i:i+batch_size]
                batch_papers = self._fetch_pubmed_details(batch_ids)
                papers.extend(batch_papers)
                
                # Add delay to respect API rate limits
                time.sleep(0.5)
            
            logger.info(f"Successfully fetched {len(papers)} papers from PubMed")
            
        except Exception as e:
            logger.error(f"Error fetching from PubMed: {e}")
        
        return papers

    def _fetch_pubmed_details(self, paper_ids: List[str]) -> List[Dict]:
        """Fetch detailed information for PubMed papers."""
        papers = []
        
        try:
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                'db': 'pubmed',
                'id': ','.join(paper_ids),
                'retmode': 'xml'
            }
            
            response = requests.get(fetch_url, params=fetch_params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            articles = root.findall('.//PubmedArticle')
            
            for article in articles:
                try:
                    paper = self._parse_pubmed_article(article)
                    if paper:
                        papers.append(paper)
                except Exception as e:
                    logger.warning(f"Error parsing PubMed article: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error fetching PubMed details: {e}")
        
        return papers

    def _parse_pubmed_article(self, article) -> Optional[Dict]:
        """Parse a PubMed article into a paper dictionary."""
        try:
            # Get title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else "No title"
            
            # Get authors and affiliations
            authors = []
            affiliations = []
            author_list = article.find('.//AuthorList')
            
            if author_list is not None:
                for author_elem in author_list.findall('Author'):
                    # Get author name
                    lastname = author_elem.find('LastName')
                    firstname = author_elem.find('ForeName')
                    
                    if lastname is not None:
                        author_name = lastname.text
                        if firstname is not None:
                            author_name = f"{firstname.text} {author_name}"
                        authors.append(author_name)
                    
                    # Get affiliations
                    affiliation_list = author_elem.find('AffiliationInfo')
                    if affiliation_list is not None:
                        for affil_elem in affiliation_list.findall('Affiliation'):
                            if affil_elem.text:
                                affiliations.append(affil_elem.text)
            
            # Get abstract
            abstract_elem = article.find('.//Abstract/AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None else ""
            
            # Get publication date
            pub_date_elem = article.find('.//PubDate')
            pub_date = ""
            if pub_date_elem is not None:
                year = pub_date_elem.find('Year')
                month = pub_date_elem.find('Month')
                day = pub_date_elem.find('Day')
                
                if year is not None:
                    pub_date = year.text
                    if month is not None:
                        pub_date += f"-{month.text}"
                        if day is not None:
                            pub_date += f"-{day.text}"
            
            # Get PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else ""
            
            # Get DOI
            doi_elem = article.find('.//ELocationID[@EIdType="doi"]')
            doi = doi_elem.text if doi_elem is not None else ""
            
            # Get journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else ""
            
            return {
                'source': 'PubMed',
                'title': title,
                'authors': authors,
                'abstract': abstract,
                'publication_date': pub_date,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                'id': pmid,
                'doi': doi,
                'journal': journal,
                'affiliations': affiliations
            }
            
        except Exception as e:
            logger.error(f"Error parsing PubMed article: {e}")
            return None

    def filter_pharma_biotech_papers(self, papers: List[Dict]) -> List[Dict]:
        """Filter papers to only include those with pharmaceutical/biotech affiliations."""
        filtered_papers = []
        
        for paper in papers:
            has_pharma_affiliation = False
            
            # Check affiliations (mainly from PubMed)
            if 'affiliations' in paper and paper['affiliations']:
                for affiliation in paper['affiliations']:
                    if self.is_pharma_biotech_affiliation(affiliation):
                        has_pharma_affiliation = True
                        break
            
            # For arXiv papers, check title and abstract for pharma/biotech keywords
            if not has_pharma_affiliation and paper['source'] == 'arXiv':
                text_to_check = f"{paper['title']} {paper['abstract']}".lower()
                for keyword in ['pharmaceutical', 'biotech', 'drug discovery', 'therapeutics', 
                               'clinical trial', 'medicine', 'pharma', 'biopharma']:
                    if keyword in text_to_check:
                        has_pharma_affiliation = True
                        break
            
            if has_pharma_affiliation:
                filtered_papers.append(paper)
        
        return filtered_papers

    def save_to_csv(self, papers: List[Dict], filename: str):
        """Save papers to CSV file."""
        if not papers:
            logger.warning("No papers to save")
            return
        
        logger.info(f"Saving {len(papers)} papers to {filename}")
        
        fieldnames = [
            'source', 'title', 'authors', 'abstract', 'publication_date', 
            'url', 'id', 'journal', 'doi', 'affiliations', 'categories'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for paper in papers:
                # Convert lists to strings for CSV
                row = {}
                
                # Copy only the fields we want in the CSV
                for field in fieldnames:
                    if field in paper:
                        if isinstance(paper[field], list):
                            row[field] = '; '.join(paper[field])
                        else:
                            row[field] = paper[field]
                    else:
                        row[field] = ''
                
                writer.writerow(row)
        
        logger.info(f"Successfully saved papers to {filename}")

    def fetch_and_filter_papers(self, query: str, max_results: int = 100, 
                               sources: List[str] = None, output_file: str = None) -> List[Dict]:
        """Main method to fetch and filter papers."""
        if sources is None:
            sources = ['pubmed', 'arxiv']
        
        all_papers = []
        
        # Fetch from PubMed
        if 'pubmed' in sources:
            pubmed_papers = self.fetch_pubmed_papers(query, max_results)
            all_papers.extend(pubmed_papers)
        
        # Fetch from arXiv
        if 'arxiv' in sources:
            arxiv_papers = self.fetch_arxiv_papers(query, max_results)
            all_papers.extend(arxiv_papers)
        
        logger.info(f"Total papers fetched: {len(all_papers)}")
        
        # Filter for pharmaceutical/biotech affiliations
        filtered_papers = self.filter_pharma_biotech_papers(all_papers)
        logger.info(f"Papers with pharma/biotech affiliations: {len(filtered_papers)}")
        
        # Save to CSV
        if output_file:
            self.save_to_csv(filtered_papers, output_file)
        
        return filtered_papers

def interactive_mode():
    """Interactive mode for easier usage."""
    print("=" * 60)
    print("Research Paper Fetcher - Interactive Mode")
    print("=" * 60)
    
    # Get search query
    query = input("\nEnter your search query: ").strip()
    if not query:
        print("Error: Search query cannot be empty")
        return
    
    # Use default values
    max_results = 100
    sources = ['pubmed', 'arxiv']
    
    # Generate output filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_query = re.sub(r'[^\w\s-]', '', query).strip()
    safe_query = re.sub(r'[-\s]+', '_', safe_query)
    default_output = f"research_papers_{safe_query}_{timestamp}.csv"
    
    output_file = input(f"Enter output filename (default: {default_output}): ").strip()
    if not output_file:
        output_file = default_output
    
    print(f"\nStarting search...")
    print(f"Query: {query}")
    print(f"Max results: {max_results}")
    print(f"Sources: {', '.join(sources)}")
    print(f"Output file: {output_file}")
    print("-" * 60)
    
    # Initialize fetcher and run
    fetcher = ResearchPaperFetcher()
    
    try:
        papers = fetcher.fetch_and_filter_papers(
            query=query,
            max_results=max_results,
            sources=sources,
            output_file=output_file
        )
        
        print(f"\n{'='*60}")
        print(f"SEARCH RESULTS FOR: {query}")
        print(f"{'='*60}")
        print(f"Total papers with pharma/biotech affiliations: {len(papers)}")
        print(f"Results saved to: {output_file}")
        
        if papers:
            print(f"\nSample results:")
            for i, paper in enumerate(papers[:3]):
                print(f"\n{i+1}. {paper['title']}")
                print(f"   Source: {paper['source']}")
                print(f"   Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")
                if paper.get('journal'):
                    print(f"   Journal: {paper['journal']}")
                if paper.get('affiliations'):
                    print(f"   Sample Affiliation: {paper['affiliations'][0][:100]}...")
        
        return papers
    
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        logger.error(f"Error during execution: {e}")
        raise

def main():
    """Main function with both command-line and interactive modes."""
    import sys
    
    # Check if running with command line arguments
    if len(sys.argv) > 1:
        # Command-line mode
        parser = argparse.ArgumentParser(description='Fetch research papers with pharmaceutical/biotech affiliations')
        parser.add_argument('query', help='Search query for papers')
        parser.add_argument('--max-results', type=int, default=100, help='Maximum number of results per source')
        parser.add_argument('--sources', nargs='+', choices=['pubmed', 'arxiv'], 
                           default=['pubmed', 'arxiv'], help='Data sources to search')
        parser.add_argument('--output', default=None, help='Output CSV filename')
        
        args = parser.parse_args()
        
        # Generate default output filename if not provided
        if args.output is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_query = re.sub(r'[^\w\s-]', '', args.query).strip()
            safe_query = re.sub(r'[-\s]+', '_', safe_query)
            args.output = f"research_papers_{safe_query}_{timestamp}.csv"
        
        # Initialize fetcher and run
        fetcher = ResearchPaperFetcher()
        
        try:
            papers = fetcher.fetch_and_filter_papers(
                query=args.query,
                max_results=args.max_results,
                sources=args.sources,
                output_file=args.output
            )
            
            print(f"\n{'='*60}")
            print(f"SEARCH RESULTS FOR: {args.query}")
            print(f"{'='*60}")
            print(f"Total papers with pharma/biotech affiliations: {len(papers)}")
            print(f"Results saved to: {args.output}")
            
            if papers:
                print(f"\nSample results:")
                for i, paper in enumerate(papers[:3]):
                    print(f"\n{i+1}. {paper['title']}")
                    print(f"   Source: {paper['source']}")
                    print(f"   Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}")
                    if paper.get('journal'):
                        print(f"   Journal: {paper['journal']}")
                    if paper.get('affiliations'):
                        print(f"   Sample Affiliation: {paper['affiliations'][0][:100]}...")
        
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
        except Exception as e:
            logger.error(f"Error during execution: {e}")
            raise
    else:
        # Interactive mode
        interactive_mode()

if __name__ == "__main__":
    main()

# Example usage:
# python research_fetcher.py "COVID-19 vaccine" --max-results 50 --sources pubmed arxiv --output covid_vaccine_papers.csv
# python research_fetcher.py "machine learning drug discovery" --max-results 100
# python research_fetcher.py "cancer therapeutics" --sources pubmed --output cancer_papers.csv