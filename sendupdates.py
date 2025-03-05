#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import json
import zipfile
import io
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# URLs to monitor
URLS = {
    "Court of Justice": "https://curia.europa.eu/en/content/juris/c2_juris.htm",
    "General Court": "https://curia.europa.eu/en/content/juris/t2_juris.htm"
}

# Email configuration
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Use app password for Gmail
EMAIL_RECEIVERS = os.getenv("EMAIL_RECEIVERS", "").split(',')
EMAIL_SUBJECT = "CURIA Website Update Alert"

# Data storage configuration
ARTIFACT_DIR = "artifact_data"  # For GitHub Actions artifacts (short-term)
PERMANENT_DIR = "permanent_data"  # For permanent storage in the repository
os.makedirs(ARTIFACT_DIR, exist_ok=True)
os.makedirs(PERMANENT_DIR, exist_ok=True)

# Print environment configuration (without password)
print(f"Environment loaded from .env file")
print(f"Email sender: {'Set' if EMAIL_SENDER else 'NOT SET'}")
print(f"Email password: {'Set' if EMAIL_PASSWORD else 'NOT SET'}")
print(f"Email receivers: {EMAIL_RECEIVERS if EMAIL_RECEIVERS else 'NOT SET'}")

def send_email(updates):
    """Send an email with new entries from both websites to multiple recipients"""
    # Check if there are any non-empty DataFrames in the updates
    has_updates = False
    for df in updates.values():
        if df is not None and not df.empty:
            has_updates = True
            break
            
    if not has_updates:
        print("No updates to send via email")
        return
    
    # Create HTML content
    html = "<h2>New entries found on CURIA websites:</h2>"
    
    for court_name, new_entries in updates.items():
        if new_entries is not None and not new_entries.empty:
            html += f"<h3>{court_name}</h3>"
            html += new_entries.to_html(index=False)
            html += f"<p>Check the website: <a href='{URLS[court_name]}'>{URLS[court_name]}</a></p>"
            html += "<hr>"
    
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['Subject'] = f"{EMAIL_SUBJECT} - {datetime.datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(html, 'html'))
    
    try:
        # Verify email configuration
        if not EMAIL_SENDER:
            raise ValueError("EMAIL_SENDER is not set in .env file")
        if not EMAIL_PASSWORD:
            raise ValueError("EMAIL_PASSWORD is not set in .env file")
        if not EMAIL_RECEIVERS:
            raise ValueError("EMAIL_RECEIVERS is not set in .env file")
            
        print(f"Using sender: {EMAIL_SENDER}")
        print(f"Recipients: {EMAIL_RECEIVERS}")
        
        # Connect to the SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        
        # Send emails to all recipients
        for receiver in EMAIL_RECEIVERS:
            receiver = receiver.strip()  # Remove any whitespace
            if receiver:  # Only send if receiver is not empty
                msg['To'] = receiver
                server.send_message(msg)
                print(f"Email sent successfully to {receiver}")
                
                # Clear the 'To' field for the next recipient
                del msg['To']
        
        server.quit()
        print(f"Email updates sent successfully to {len(EMAIL_RECEIVERS)} recipients")
    except Exception as e:
        import traceback
        print(f"Failed to send email: {str(e)}")
        print("Error details:")
        traceback.print_exc()

def get_current_data(url):
    """Scrape and parse the current data from a website"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            print(f"No table found on the website: {url}")
            return pd.DataFrame()
        
        # Extract table headers
        headers = ["id", "description"]
        
        # Extract table rows
        rows = []
        for tr in table.find_all('tr')[1:]:  # Skip header row
            row = []
            for td in tr.find_all('td'):
                row.append(td.text.strip())
            if row:  # Only add non-empty rows
                rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=headers).query("id != ''")
        print(f"Successfully scraped {len(df)} entries from {url}")
        return df
    
    except Exception as e:
        print(f"Error scraping website {url}: {str(e)}")
        return pd.DataFrame()

def get_data_filename(court_name, permanent=False):
    """Generate a filename for storing data for a specific court
    
    Args:
        court_name: Name of the court
        permanent: If True, use permanent storage directory, otherwise use artifact directory
    """
    directory = PERMANENT_DIR if permanent else ARTIFACT_DIR
    return os.path.join(directory, f"{court_name.replace(' ', '_').lower()}_data.csv")

def check_for_previous_data():
    """
    Check for previous data from either permanent storage or the artifact
    
    Returns:
        tuple: (has_data, source) where source is 'permanent', 'artifact', or None
    """
    # First, check permanent storage
    print(f"Checking for previous data in permanent storage ({PERMANENT_DIR})")
    has_permanent_data = os.path.exists(PERMANENT_DIR) and any(
        os.path.exists(get_data_filename(court, permanent=True)) for court in URLS.keys()
    )
    
    if has_permanent_data:
        print("Found previous data in permanent storage")
        # Copy permanent data to artifact directory to ensure we're working with the latest data
        for court_name in URLS.keys():
            permanent_file = get_data_filename(court_name, permanent=True)
            artifact_file = get_data_filename(court_name, permanent=False)
            if os.path.exists(permanent_file):
                import shutil
                print(f"Copying permanent data for {court_name} to working directory")
                shutil.copy2(permanent_file, artifact_file)
        return True, 'permanent'
    
    # If no permanent data, check artifact
    print(f"Checking for previous artifact data in {ARTIFACT_DIR}")
    has_artifact_data = os.path.exists(ARTIFACT_DIR) and any(
        os.path.exists(get_data_filename(court, permanent=False)) for court in URLS.keys()
    )
    
    if has_artifact_data:
        print("Found previous data in artifact storage")
        return True, 'artifact'
    
    print("No previous data found in either location")
    return False, None

def check_for_updates():
    """Check for updates on all websites and save current data for future comparisons"""
    updates = {}
    
    # Check for previous data in either permanent or artifact storage
    has_previous_data, data_source = check_for_previous_data()
    
    for court_name, url in URLS.items():
        print(f"Checking for updates on {court_name} website")
        current_data = get_current_data(url)
        data_file = get_data_filename(court_name)
        
        if current_data.empty:
            print(f"No data retrieved from {court_name} website")
            updates[court_name] = None
            continue
        
        # Ensure we have columns to work with
        if len(current_data.columns) == 0:
            print(f"No columns found in data for {court_name}")
            updates[court_name] = None
            continue
            
        # Use the first column as unique ID
        id_column = current_data.columns[0]
        print(f"Using '{id_column}' as unique identifier")
        
        # Load previous data if exists
        if has_previous_data and os.path.exists(data_file):
            try:
                previous_data = pd.read_csv(data_file)
                
                # Check if the ID column exists in previous data
                if id_column not in previous_data.columns:
                    print(f"ID column '{id_column}' not found in previous data. Creating new reference data.")
                    current_data.to_csv(data_file, index=False)
                    print(f"Created new reference data with {len(current_data)} entries")
                    updates[court_name] = current_data
                    continue
                
                # Convert ID columns to strings for comparison
                current_ids = set(current_data[id_column].astype(str))
                previous_ids = set(previous_data[id_column].astype(str))
                
                # Find new entries
                new_ids = current_ids - previous_ids
                
                if new_ids:
                    # Find rows with new IDs
                    new_entries = current_data[current_data[id_column].astype(str).isin(new_ids)]
                    
                    print(f"Found {len(new_entries)} new entries for {court_name}")
                    updates[court_name] = new_entries
                    
                    # Update reference file with all current data
                    current_data.to_csv(data_file, index=False)
                    print(f"Updated reference data with {len(current_data)} total entries")
                    
                    # Also save to permanent storage
                    permanent_file = get_data_filename(court_name, permanent=True)
                    current_data.to_csv(permanent_file, index=False)
                    print(f"Updated permanent storage with {len(current_data)} entries")
                else:
                    print(f"No new entries found for {court_name}")
                    updates[court_name] = pd.DataFrame(columns=current_data.columns)
                    
                    # Still save current data to keep timestamps updated
                    current_data.to_csv(data_file, index=False)
                    
                    # Also update permanent storage
                    permanent_file = get_data_filename(court_name, permanent=True)
                    current_data.to_csv(permanent_file, index=False)
                    
            except Exception as e:
                print(f"Error processing previous data: {str(e)}")
                import traceback
                traceback.print_exc()
                print("Creating new reference data...")
                
                # Save current data as reference
                current_data.to_csv(data_file, index=False)
                print(f"Created new reference data with {len(current_data)} entries")
                
                # Also save to permanent storage
                permanent_file = get_data_filename(court_name, permanent=True)
                current_data.to_csv(permanent_file, index=False)
                print(f"Created permanent storage data with {len(current_data)} entries")
                
                updates[court_name] = current_data
        else:
            print(f"No previous data file found for {court_name}. Creating new reference data.")
            
            # Save current data as reference
            current_data.to_csv(data_file, index=False)
            print(f"Created new reference data with {len(current_data)} entries")
            
            # Also save to permanent storage
            permanent_file = get_data_filename(court_name, permanent=True)
            current_data.to_csv(permanent_file, index=False)
            print(f"Created permanent storage data with {len(current_data)} entries")
            
            updates[court_name] = current_data
    
    # Send email with all updates
    send_email(updates)
    
    print(f"Completed data analysis. Artifact data saved to {ARTIFACT_DIR}")
    print(f"Permanent data saved to {PERMANENT_DIR}")
    # In a GitHub Actions workflow:
    # - The artifact directory will be uploaded as a temporary artifact
    # - The permanent directory will be committed back to the repository

if __name__ == "__main__":
    print(f"--- Running CURIA website check at {datetime.datetime.now()} ---")
    check_for_updates()
    print("--- Check complete ---")
