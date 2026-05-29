import os, re, smtplib, requests
from bs4 import BeautifulSoup
from email.mime.text import MIMEText

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO = os.getenv("EMAIL_TO")

MIN_VALUE = 5000000  # 50 lakh

INCLUDE = [
    "rcc road", "cc road", "road construction",
    "building construction", "infrastructure",
    "prefab", "prefabricated", "civil work", "civil works"
]

EXCLUDE = [
    "maintenance", "repair", "renewal",
    "o&m", "operation and maintenance"
]

SITES = [
    "https://eprocure.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
    "https://etenders.gov.in/eprocure/app?page=FrontEndLatestActiveTenders&service=page",
    "https://etenders.hry.nic.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    "https://defproc.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
    "https://pmgsytenders.gov.in/nicgep/app?page=FrontEndLatestActiveTenders&service=page",
]

def clean(text):
    return " ".join(text.split())

def match_tender(text):
    t = text.lower()
    if any(x in t for x in EXCLUDE):
        return False
    return any(x in t for x in INCLUDE)

def value_ok(text):
    t = text.replace(",", "").lower()
    nums = re.findall(r"\d+(?:\.\d+)?", t)

    if not nums:
        return True

    for n in nums:
        val = float(n)
        if "crore" in t or " cr" in t:
            if val * 10000000 >= MIN_VALUE:
                return True
        elif "lakh" in t or "lac" in t:
            if val * 100000 >= MIN_VALUE:
                return True
        elif val >= MIN_VALUE:
            return True

    return True

def fetch_tenders():
    results = []

    for url in SITES:
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            soup = BeautifulSoup(r.text, "html.parser")

            for row in soup.find_all("tr"):
                text = clean(row.get_text(" ", strip=True))

                if len(text) < 40:
                    continue

                if match_tender(text) and value_ok(text):
                    results.append({
                        "site": url,
                        "text": text[:700]
                    })

        except Exception as e:
            results.append({
                "site": url,
                "text": f"Error checking site: {e}"
            })

    return results

def send_email(tenders):
    if tenders:
        subject = f"Daily Tender Alert: {len(tenders)} matching tenders found"
        body = "Aaj ke matching tenders:\n\n"

        for i, t in enumerate(tenders[:50], 1):
            body += f"{i}. {t['text']}\n"
            body += f"Portal: {t['site']}\n\n"
    else:
        subject = "Daily Tender Alert: No matching tenders found"
        body = "Aaj RCC Road / Building / Infra / Prefab ke matching tenders nahi mile."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

if __name__ == "__main__":
    tenders = fetch_tenders()
    send_email(tenders)
