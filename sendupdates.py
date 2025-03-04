import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(
    filename='curia_monitor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# URLs to monitor
URLS = {
    "Court of Justice": "https://curia.europa.eu/en/content/juris/c2_juris.htm",
    "General Court": "https://curia.europa.eu/en/content/juris/t2_juris.htm"
}

# Directory to store previous data
DATA_DIR = "curia_data"
os.makedirs(DATA_DIR, exist_ok=True)

# Email configuration
EMAIL_SENDER = os.getenv("USER_EMAIL")
EMAIL_PASSWORD = os.getenv("USER_PASSWORD")  # Use app password for Gmail
EMAIL_RECEIVERS = os.getenv("RECEIVER_EMAILS").split(',')  # Comma-separated list of email addresses
EMAIL_SUBJECT = "CURIA Website Update Alert"

def send_email(updates):
    """Send an email with new entries from both websites to multiple recipients"""
    # Check if there are any non-empty DataFrames in the updates
    has_updates = False
    for df in updates.values():
        if df is not None and not df.empty:
            has_updates = True
            break
            
    if not has_updates:
        logging.info("No updates to send via email")
        return
    
    # Create HTML content
    html = "<h2>New entries found on CURIA websites:</h2>"
    
    for court_name, new_entries in updates.items():
        if new_entries is not None and not new_entries.empty:
            html += f"<h3>{court_name}</h3>"
            html += new_entries.to_html()
            html += f"<p>Check the website: <a href='{URLS[court_name]}'>{URLS[court_name]}</a></p>"
            html += "<hr>"
    
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['Subject'] = f"{EMAIL_SUBJECT} - {datetime.datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(html, 'html'))
    
    try:
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
                logging.info(f"Email sent successfully to {receiver}")
                
                # Clear the 'To' field for the next recipient
                del msg['To']
        
        server.quit()
        logging.info(f"Email updates sent successfully to {len(EMAIL_RECEIVERS)} recipients")
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")

def get_current_data(url):
    """Scrape and parse the current data from a website"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            logging.warning(f"No table found on the website: {url}")
            return pd.DataFrame()
        
        # Extract table headers
        headers = []
        for th in table.find_all('th'):
            headers.append(th.text.strip())
        
        # Extract table rows
        rows = []
        for tr in table.find_all('tr')[1:]:  # Skip header row
            row = []
            for td in tr.find_all('td'):
                row.append(td.text.strip())
            if row:  # Only add non-empty rows
                rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(rows, columns=headers)
        logging.info(f"Successfully scraped {len(df)} entries from {url}")
        return df
    
    except Exception as e:
        logging.error(f"Error scraping website {url}: {str(e)}")
        return pd.DataFrame()

def get_data_filename(court_name):
    """Generate a filename for storing data for a specific court"""
    return os.path.join(DATA_DIR, f"{court_name.replace(' ', '_').lower()}_data.csv")

def check_for_updates():
    """Check for updates on all websites and send email if new entries are found"""
    updates = {}
    
    for court_name, url in URLS.items():
        logging.info(f"Checking for updates on {court_name} website")
        current_data = get_current_data(url)
        data_file = get_data_filename(court_name)
        
        if current_data.empty:
            logging.warning(f"No data retrieved from {court_name} website")
            updates[court_name] = None
            continue
        
        # Load previous data if exists
        if os.path.exists(data_file):
            previous_data = pd.read_csv(data_file)
            
            # Compare data to find new entries
            if len(current_data.columns) == len(previous_data.columns):
                # Convert DataFrames to sets of tuples for comparison
                current_set = set(map(tuple, current_data.values))
                previous_set = set(map(tuple, previous_data.values))
                
                # Find new entries
                new_entries_set = current_set - previous_set
                
                if new_entries_set:
                    # Convert back to DataFrame
                    new_entries = pd.DataFrame(list(new_entries_set), columns=current_data.columns)
                    logging.info(f"Found {len(new_entries)} new entries for {court_name}")
                    updates[court_name] = new_entries
                else:
                    logging.info(f"No new entries found for {court_name}")
                    updates[court_name] = pd.DataFrame()
            else:
                logging.warning(f"Column mismatch between current and previous data for {court_name}")
                # Save current data as new reference
                current_data.to_csv(data_file, index=False)
                updates[court_name] = current_data  # Consider all entries as new
        else:
            logging.info(f"No previous data file found for {court_name}. Creating new reference file.")
            # First run, save current data as reference
            current_data.to_csv(data_file, index=False)
            updates[court_name] = current_data  # Consider all entries as new
        
        # Update the reference file with current data
        current_data.to_csv(data_file, index=False)
    
    # Send email with all updates
    send_email(updates)

def main():
    """Main function to run daily checks"""
    logging.info("Starting CURIA websites monitor")
    
    while True:
        check_for_updates()
        
        # Wait for 24 hours before checking again
        next_check = datetime.datetime.now() + datetime.timedelta(days=1)
        logging.info(f"Next check scheduled for: {next_check}")
        
        time.sleep(24 * 60 * 60)  # Sleep for 24 hours

if __name__ == "__main__":
    main()
