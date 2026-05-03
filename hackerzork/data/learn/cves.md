# CVES — Common Vulnerabilities and Exposures

A CVE is a unique identifier for one specific publicly-disclosed
vulnerability. Format:

    CVE-YYYY-NNNNN    e.g.  CVE-2021-23017  (a real nginx DNS bug)

Two pieces of information always go together:

  1. The CVE id (the bug)
  2. The affected software + version range

A vulnerability that doesn't apply to the version in front of you isn't
exploitable. Step one of any engagement is fingerprinting versions.

## How a CVE becomes useful

  ┌─ enumerate ──┐    ┌─ research ──┐    ┌─ exploit ──┐
  │ nmap -sV     │ -> │ search CVE  │ -> │ exploit    │
  │ → versions   │    │ for version │    │ -p PORT    │
  └──────────────┘    └─────────────┘    │ -e CVE     │
                                         └────────────┘

The middle step is where most learning happens. Real-world resources:

  nvd.nist.gov                 official US registry, CVSS scores
  cve.mitre.org                source-of-truth ids and descriptions
  github.com/.../poc           proof-of-concept exploit code
  exploit-db.com               curated exploit archive
  vulners.com / cvedetails     fast cross-referenced search

## CVSS — severity score

Each CVE comes with a CVSS vector and a 0.0–10.0 score:

  9.0–10.0  CRITICAL  — typically RCE, no auth, low complexity
  7.0–8.9   HIGH
  4.0–6.9   MEDIUM
  0.1–3.9   LOW

Critical doesn't mean "easy" — it means "high impact if exploited". An
unauth pre-auth RCE on an internet-exposed service is the worst kind.

## Patch lag is the attack window

The mean time-to-patch in the wild is measured in WEEKS. Attackers scan
for the CVE within hours of disclosure. The defender's job is to shrink
that window; the attacker's job is to find the systems that haven't.

## In this game

CVEs in node YAML are real-flavored but invented for the world. The
mechanics mirror real exploitation: enumerate, look up, exploit.

## See also

  man nmap          man exploit       learn port-scanning
