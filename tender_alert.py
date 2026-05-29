import os
import re
import smtplib
import requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText
from urllib.parse import urljoin

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

MIN_VALUE = 5000000  # 50 lakh

INCLUDE = [
    "rcc", "rcc road", "cc road",
    "road construction", "road work",
    "building construction", "building work",
    "civil work", "civil works",
    "infrastructure", "infra",
    "prefab", "prefabricated", "peb",
    "pwd", "cpwd", "smart city"
]

STRONG_INCLUDE = [
    "rcc road", "cc road", "road construction",
    "building construction", "prefab",
    "prefabricated", "peb"
]

EXCLUDE = [
    "maintenance", "repair", "renewal",
    "o&m", "operation and maintenance",
    "amc", "supply", "hiring", "consultancy",
    "manpower", "vehicle", "furniture"
]

SKIP_TEXT = [
    "contents owned",
    "contents owned and maintained",
    "national rural roads development agency",
    "visitor no",
    "portal policies",
    "screen reader",
    "site best viewed",
    "copyright",
    "terms and conditions",
    "privacy policy",
    "hyperlinking policy",
    "web information manager"
]

SITES = [
    {
        "name": "Central eProcure",
        "url": "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page"
    },
    {
        "name": "eTenders India",
        "url": "https://etenders.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page"
    },
    {
        "name": "Haryana eTenders",
        "url": "https://etenders.hry.nic.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    },
    {
        "name": "Defence eProcurement",
        "url": "https://defproc.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    },
    {
        "name": "PMGSY",
        "url": "https://pmgsytenders.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page"
    },
]

def clean(text):
    return " ".join(text.split())

def contains_any(text, words):
    t = text.lower()
    return any(w in t for w in words)

def get_value(text):
    t = text.replace(",", "").lower()

    crore = re.search(r"(\d+(?:\.\d+)?)\s*(crore|cr)", t)
    if crore:
        return int(float(crore.group(1)) * 10000000)

    lakh = re.search(r"(\d+(?:\.\d+)?)\s*(lakh|lac)", t)
    if lakh:
        return int(float(lakh.group(1)) * 100000)

    rupee = re.search(r"(?:rs\.?|inr|₹)\s*(\d+(?:\.\d+)?)", t)
    if rupee:
        return int(float(rupee.group(1)))

    big_number = re.findall(r"\b\d{6,}\b", t)
    if big_number:
        return max(int(x) for x in big_number)

    return None

def is_real_tender_row(text):
    t = text.lower()

    if len(t) < 50:
        return False

    if contains_any(t, SKIP_TEXT):
        return False

    if contains_any(t, EXCLUDE):
        return False

    has_work_keyword = contains_any(t, INCLUDE)

    has_tender_signal = any(x in t for x in [
        "tender", "bid", "nit", "work", "closing",
        "submission", "published", "organisation",
        "organization", "department"
    ])

    return has_work_keyword and has_tender_signal

def value_filter(text):
    value = get_value(text)

    if value is None:
        return contains_any(text, STRONG_INCLUDE)

    if value >= MIN_VALUE:
        return True

    return contains_any(text, STRONG_INCLUDE)

def extract_link(row, page_url):
    a = row.find("a", href=True)
    if not a:
        return page_url

    href = a.get("href", "").strip()
    if not href or href.startswith("javascript"):
        return page_url

    return urljoin(page_url, href)

def fetch_tenders():
    results = []
    seen = set()

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for site in SITES:
        name = site["name"]
        url = site["url"]

        try:
            r = requests.get(url, timeout=30, headers=headers)
            soup = BeautifulSoup(r.text, "html.parser")

            rows = soup.find_all("tr")
            
            print(f"{name} -> Total Rows Found: {len(rows)}")
            
            for row in rows:
                text = clean(row.get_text(" ", strip=True))

                if len(text) > 50:
                    print(text[:150])
                
                if not is_real_tender_row(text):
                    continue

                if not value_filter(text):
                    continue

                link = extract_link(row, url)

                key = text[:180].lower()
                if key in seen:
                    continue
                seen.add(key)

                value = get_value(text)

                results.append({
                    "portal": name,
                    "text": text[:900],
                    "value": value,
                    "link": link
                })

        except Exception as e:
            results.append({
                "portal": name,
                "text": f"Error checking portal: {e}",
                "value": None,
                "link": url
            })

    return results

def format_value(value):
    if value is None:
        return "Not found"

    if value >= 10000000:
        return f"₹{value / 10000000:.2f} Cr"

    if value >= 100000:
        return f"₹{value / 100000:.2f} Lakh"

    return f"₹{value}"

def send_email(tenders):
    if tenders:
        subject = f"Daily Tender Alert: {len(tenders)} useful tenders found"
        body = "Aaj ke matching tenders:\n\n"

        for i, t in enumerate(tenders[:50], 1):
            body += f"{i}. Portal: {t['portal']}\n"
            body += f"Value: {format_value(t['value'])}\n"
            body += f"Details: {t['text']}\n"
            body += f"Link: {t['link']}\n"
            body += "-" * 60 + "\n\n"
    else:
        subject = "Daily Tender Alert: No matching tenders found"
        body = (
            "Aaj RCC Road / Building / Infra / Prefab ke useful tenders nahi mile.\n\n"
            "Note: Agar kisi portal par CAPTCHA ya JavaScript table hai, to simple scanner us data ko nahi padh payega."
        )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

if __name__ == "__main__":
    tenders = fetch_tenders()
    send_email(tenders)
