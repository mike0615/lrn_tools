# LRN Tools

A growing collection of infrastructure automation tools built for the **Local Restricted Network (LRN)** — an air-gapped, enterprise-grade lab environment running Rocky Linux, FreeIPA, BIND 9, XCP-ng, and related open-source infrastructure.

These tools are designed to be:
- **Air-gap friendly** — no external dependencies, no internet required at runtime
- **Production-ready** — structured output, proper error handling, BIND-compatible zone files
- **Operator-focused** — built by a systems engineer, for systems engineers

---

## Repository Layout

```
lrn_tools/
├── tools/
│   └── dns/
│       └── gen-reverse-zones.py   # Generate BIND 9 reverse zones from a forward zone
├── docs/
│   ├── how-to-use.md              # Detailed usage guide for all tools
│   └── release-notes.md           # Version history and changelog
└── README.md
```

---

## Tools

| Tool | Category | Description |
|------|----------|-------------|
| [gen-reverse-zones.py](tools/dns/gen-reverse-zones.py) | DNS | Parses a BIND 9 forward zone file and generates reverse lookup zones with PTR records |

---

## Requirements

- Python 3.6+
- Standard library only (no pip installs required)
- BIND 9 (for consuming the output)

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/mike0615/lrn_tools.git
cd lrn_tools

# Generate reverse zones from an existing forward zone
python3 tools/dns/gen-reverse-zones.py /var/named/db.example.com \
    -o /var/named \
    --print-conf
```

See [docs/how-to-use.md](docs/how-to-use.md) for full documentation on each tool.

---

## Contributing / Adding Tools

This repo is intentionally structured so new tools drop in cleanly:

1. Create a subdirectory under `tools/` for the category (e.g., `tools/ldap/`, `tools/pki/`)
2. Add the script with a descriptive name
3. Update the table above in this README
4. Add a section to `docs/how-to-use.md`
5. Add an entry to `docs/release-notes.md`

---

## License

MIT — see individual tool headers for specifics.
