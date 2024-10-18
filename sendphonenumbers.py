from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import ssl
from dotenv import load_dotenv
import requests
import os
from bs4 import BeautifulSoup as bs

# Load environment variables
load_dotenv()

def parse_header(raw_header: str):
    header = {}

    for line in raw_header.split("-H"):

        a, b = line.split(":",1)
        
        header[a.strip(" '")] = b.strip(" '")

    return header

def parse_spusu():

    url = 'https://www.spusu.at/bestellen' 

    raw_header = "'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0' -H 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,image/svg+xml,*/*;q=0.8' -H 'Accept-Language: en-US,en;q=0.5' -H 'Accept-Encoding: gzip, deflate, br, zstd' -H 'DNT: 1' -H 'Connection: keep-alive' -H 'Cookie: MVNOTrC=tarife.at; MVNOTrUid=1291ed1c3e5d4b0dd762; acceptSpusuCookies=true; CMSLocale=de-AT; JSESSIONID=C240088542FB655DE51A6DA669D2C49F; mrsroute=.SERVER1; MVNOOr0=MTNmMDNjY2E5ZTE2MTk5MWFiM2YyZjFkNGNkYmYzMGQzMmZiMGUxZjZmMjFmMzc0ODRhNWE5OGNhMDYzZTBjYXsib3JkZXJndWlkIjoiMjlmYTgzMzBhNyIsInJlZmVyZXIiOiJ0YXJpZmUuYXQiLCJjdXJyZW50U3RlcCI6IlN0ZXBEYXRhIiwiaXNJbnRlcm5hbE9yZGVyIjpmYWxzZSwib3JkZXJUeXBlIjoiT1JERVIiLCJvcmRlcmVkVGFyaWZmTW9kZWxzIjp7IjAiOjE4OTh9LCJvcmRlcmVkRGV2aWNlcyI6e30sImNvbWJpbmF0aW9uRGlzY291bnRCeVRhcmlmZk1vZGVsSW5kZXgiOnt9LCJjb21iaW5hdGlvblRhcmlmZk1vZGVsSW5kZXhCeURldmljZUluZGV4Ijp7fSwiY29tYmluYXRpb25EZXZpY2VJbmRleEJ5VGFyaWZmTW9kZWxJbmRleCI6e30sInBvc3NpYmxlTnVtYmVycyI6eyIwIjp7IjQ1ODU4NDYzIjoiKzQzNjcwMTkwNjcwNyIsIjM4MDUxMDIxIjoiKzQzNjcwMzU5MTkzOSIsIjQ1OTYxMTExIjoiKzQzNjcwMTkwNjg5MSIsIjQ1ODY1NTY5IjoiKzQzNjcwMTkwNjg5MyIsIjQ1ODM0NTE5IjoiKzQzNjcwMTkwNjUxNiIsIjQ1OTcxNjgxIjoiKzQzNjcwMTkwNjIwOSIsIjQ1OTUzNzQ1IjoiKzQzNjcwMTkwNjI5NCIsIjUwODYyMjI5IjoiKzQzNjcwMzU5MTk0NSIsIjQ1ODU2ODA1IjoiKzQzNjcwMTkwNjI1MyIsIjQ1ODk0MDk5IjoiKzQzNjcwMTkwNjgxMyJ9fSwiY2hvc2VuTnVtYmVycyI6e30sImRpc2NvdW50QW1vdW50IjowLCJjdXN0b21lckRhdGEiOnt9LCJ1c2VQYXltZW50TWV0aG9kRm9yQXV0b21hdGljUmVjaGFyZ2UiOnRydWUsImNvbnZlcnNpb25Eb25lIjpmYWxzZX0=' -H 'Upgrade-Insecure-Requests: 1' -H 'Sec-Fetch-Dest: document' -H 'Sec-Fetch-Mode: navigate' -H 'Sec-Fetch-Site: none' -H 'Sec-Fetch-User: ?1' -H 'Priority: u=0, i' -H 'TE: trailers'"

    header = parse_header(raw_header)

    r = requests.get(url, headers=header).text
    
    # get the phone numbers available
    numbers = [x.text for x in bs(r).select("#selectnewNumberSelect0 option")]
    
    # count the unique characters in the phone number
    counts = {}
    for n in numbers:
        counts[n] = len(set(n))

    # sort the dictionary based on the unique numbers in the phone numbers
    c = []
    for n, count in dict(sorted(counts.items(), key=lambda item: item[1])).items():
        c.append(f"{n} : {count} unique characters")

    # return phone numbers as a plaintext list
    results = '\n'.join(c)

    return results

def send_email():

    subject="Chose a phone number"
    body= parse_spusu()

    port = 465  # For SSL
    smtp_server = "smtp.gmail.com"
    USERNAME = os.getenv("USER_EMAIL")
    PASSWORD = os.getenv("USER_PASSWORD")

    messagestring = f"Subject: {subject}\n\n{body}"
    print(messagestring)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
            server.login(USERNAME, PASSWORD)
            server.sendmail(USERNAME, USERNAME, messagestring)
            print("Email sent successfully")
    except Exception as e:
        print("Error sending email: ", e)


send_email()
