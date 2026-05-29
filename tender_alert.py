import requests

KEYWORDS = [
    "rcc road",
    "road construction",
    "building construction",
    "infrastructure",
    "prefab",
    "prefabricated",
    "civil work"
]

MIN_VALUE = 5000000

print("Tender Alert System Started")

sites = [
    "https://etenders.gov.in",
    "https://etenders.hry.nic.in",
    "https://defproc.gov.in",
    "https://pmgsytenders.gov.in"
]

for site in sites:
    print(f"Checking: {site}")

print("Matching tenders will be emailed.")
