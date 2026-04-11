#!/usr/bin/env python3
"""
gen-reverse-zones.py — Generate BIND 9 reverse lookup zones from a forward zone file.

Usage:
    python3 gen-reverse-zones.py <forward-zone-file> [options]

Options:
    -o, --output-dir DIR     Directory to write reverse zone files (default: current dir)
    -n, --nameserver NS      Primary nameserver FQDN (overrides SOA detection)
    -e, --email EMAIL        Hostmaster email (overrides SOA detection, use dot notation)
    -t, --ttl TTL            TTL for reverse zone (default: inherited from forward zone)
    -p, --prefix             Print named.conf zone stanza(s) for each reverse zone
    --dry-run                Print output to stdout instead of writing files
"""

import argparse
import ipaddress
import os
import re
import sys
from collections import defaultdict
from datetime import datetime


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def strip_comment(line):
    """Remove inline ; comments, respecting quoted strings."""
    in_quote = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
        if ch == ';' and not in_quote:
            return line[:i].rstrip()
    return line.rstrip()


def parse_zone_file(path):
    """
    Parse a BIND 9 forward zone file.
    Returns:
        origin (str)         — zone origin (FQDN with trailing dot)
        ttl    (str)         — default TTL string
        soa    (dict)        — mname, rname, serial, refresh, retry, expire, minimum
        ns     (list)        — list of NS FQDN strings
        a_records (list)     — list of (fqdn, ip_str) tuples
        aaaa_records (list)  — list of (fqdn, ipv6_str) tuples
    """
    origin = None
    default_ttl = "86400"
    soa = {}
    ns_records = []
    a_records = []
    aaaa_records = []

    current_name = None
    current_ttl = None

    # Flatten multi-line parenthesised blocks first
    with open(path, 'r') as fh:
        raw = fh.read()

    # Replace parenthesised newlines with spaces so each logical record is one line
    flat = re.sub(r'\(([^)]*)\)', lambda m: '(' + m.group(1).replace('\n', ' ') + ')', raw)

    for raw_line in flat.splitlines():
        line = strip_comment(raw_line)
        if not line:
            continue

        # $ORIGIN
        m = re.match(r'^\$ORIGIN\s+(\S+)', line, re.IGNORECASE)
        if m:
            origin = m.group(1).rstrip('.')  + '.'
            continue

        # $TTL
        m = re.match(r'^\$TTL\s+(\S+)', line, re.IGNORECASE)
        if m:
            default_ttl = m.group(1)
            continue

        # Tokenise
        tokens = line.split()
        if not tokens:
            continue

        # Determine name field — if line starts with whitespace, name is inherited
        if raw_line and raw_line[0] in (' ', '\t'):
            name = current_name
            idx = 0
        else:
            name = tokens[0]
            current_name = name
            idx = 1

        # Skip optional TTL and optional class
        ttl_val = current_ttl or default_ttl
        while idx < len(tokens):
            # TTL-like token (digits or Ns/Mm/Hh/Dd/Ww notation)
            if re.match(r'^\d+[smhdwSMHDW]?$', tokens[idx]):
                ttl_val = tokens[idx]
                idx += 1
                continue
            # Class token
            if tokens[idx].upper() in ('IN', 'CHAOS', 'HS', 'ANY'):
                idx += 1
                continue
            break

        if idx >= len(tokens):
            continue

        rtype = tokens[idx].upper()
        idx += 1
        rdata = tokens[idx:]

        # Resolve the record name to a FQDN
        def to_fqdn(label):
            if label == '@':
                return origin or '.'
            if label.endswith('.'):
                return label
            if origin:
                return label + '.' + origin
            return label + '.'

        fqdn = to_fqdn(name) if name else None

        # SOA
        if rtype == 'SOA' and len(rdata) >= 7:
            # SOA mname rname ( serial refresh retry expire minimum )
            # After paren-flattening: mname rname serial refresh retry expire minimum
            mname = rdata[0]
            rname = rdata[1]
            # strip parens that may still be adjacent
            fields = [t.strip('()') for t in rdata[2:] if t.strip('()')]
            soa = {
                'mname': mname if mname.endswith('.') else mname + '.' + (origin or ''),
                'rname': rname if rname.endswith('.') else rname + '.' + (origin or ''),
                'serial': fields[0] if len(fields) > 0 else '1',
                'refresh': fields[1] if len(fields) > 1 else '3600',
                'retry':   fields[2] if len(fields) > 2 else '900',
                'expire':  fields[3] if len(fields) > 3 else '604800',
                'minimum': fields[4] if len(fields) > 4 else '86400',
            }
            continue

        # NS
        if rtype == 'NS' and rdata:
            ns = rdata[0]
            if not ns.endswith('.'):
                ns = ns + '.' + (origin or '')
            ns_records.append(ns)
            continue

        # A
        if rtype == 'A' and rdata and fqdn:
            try:
                ipaddress.IPv4Address(rdata[0])
                a_records.append((fqdn, rdata[0]))
            except ValueError:
                print(f"  [WARN] Skipping invalid A record value: {rdata[0]}", file=sys.stderr)
            continue

        # AAAA
        if rtype == 'AAAA' and rdata and fqdn:
            try:
                ipaddress.IPv6Address(rdata[0])
                aaaa_records.append((fqdn, rdata[0]))
            except ValueError:
                print(f"  [WARN] Skipping invalid AAAA record value: {rdata[0]}", file=sys.stderr)
            continue

    return origin, default_ttl, soa, ns_records, a_records, aaaa_records


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------

def group_by_network_v4(a_records):
    """
    Group A records by their /24 reverse zone.
    Returns dict: '1.168.192.in-addr.arpa.' -> [(fqdn, ip), ...]
    """
    groups = defaultdict(list)
    for fqdn, ip in a_records:
        parts = ip.split('.')
        rev_zone = f"{parts[2]}.{parts[1]}.{parts[0]}.in-addr.arpa."
        groups[rev_zone].append((fqdn, ip))
    return dict(groups)


def group_by_network_v6(aaaa_records):
    """
    Group AAAA records by their /64 reverse zone (nibble notation).
    Returns dict: '<nibbles>.ip6.arpa.' -> [(fqdn, ip6_str), ...]
    """
    groups = defaultdict(list)
    for fqdn, ip6 in aaaa_records:
        addr = ipaddress.IPv6Address(ip6)
        # Full 32-nibble exploded form
        nibbles = addr.exploded.replace(':', '')
        # Reverse all 32 nibbles, take first 16 (the /64 prefix) for the zone name
        rev_all = '.'.join(reversed(nibbles))
        # Zone is the last 16 nibbles of the reversed string (the prefix half)
        zone_nibbles = '.'.join(list(reversed(nibbles))[:16])
        zone = zone_nibbles + '.ip6.arpa.'
        groups[zone].append((fqdn, ip6))
    return dict(groups)


# ---------------------------------------------------------------------------
# Zone file generation
# ---------------------------------------------------------------------------

def next_serial():
    """YYYYMMDDnn-style serial using today's date."""
    return datetime.now().strftime('%Y%m%d01')


def build_reverse_zone_v4(rev_zone, records, soa, ns_records, default_ttl):
    """Return the text of a reverse zone file for a /24 IPv4 block."""
    mname   = soa.get('mname', 'ns1.' + (soa.get('rname', 'example.com.')))
    rname   = soa.get('rname', 'hostmaster.example.com.')
    serial  = next_serial()
    refresh = soa.get('refresh', '3600')
    retry   = soa.get('retry',   '900')
    expire  = soa.get('expire',  '604800')
    minimum = soa.get('minimum', '86400')

    ns_lines = '\n'.join(f"\t\t\tIN\tNS\t{ns}" for ns in (ns_records or [mname]))

    ptr_lines = []
    for fqdn, ip in sorted(records, key=lambda r: int(r[1].split('.')[3])):
        last_octet = ip.split('.')[3]
        ptr_lines.append(f"{last_octet}\t\t\tIN\tPTR\t{fqdn}")

    return f"""\
; Reverse lookup zone: {rev_zone}
; Generated by gen-reverse-zones.py on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
;
$TTL {default_ttl}
$ORIGIN {rev_zone}

@\t\t\tIN\tSOA\t{mname} {rname} (
\t\t\t\t{serial}\t; Serial
\t\t\t\t{refresh}\t\t; Refresh
\t\t\t\t{retry}\t\t\t; Retry
\t\t\t\t{expire}\t\t; Expire
\t\t\t\t{minimum} )\t\t; Negative cache TTL

; Name Servers
{ns_lines}

; PTR Records
{chr(10).join(ptr_lines)}
"""


def build_reverse_zone_v6(rev_zone, records, soa, ns_records, default_ttl):
    """Return the text of a reverse zone file for a /64 IPv6 block."""
    mname   = soa.get('mname', 'ns1.example.com.')
    rname   = soa.get('rname', 'hostmaster.example.com.')
    serial  = next_serial()
    refresh = soa.get('refresh', '3600')
    retry   = soa.get('retry',   '900')
    expire  = soa.get('expire',  '604800')
    minimum = soa.get('minimum', '86400')

    ns_lines = '\n'.join(f"\t\t\tIN\tNS\t{ns}" for ns in (ns_records or [mname]))

    ptr_lines = []
    for fqdn, ip6 in records:
        addr = ipaddress.IPv6Address(ip6)
        nibbles = addr.exploded.replace(':', '')
        rev_nibbles = '.'.join(reversed(nibbles))
        # The PTR owner name relative to the /64 zone is the host portion (last 16 nibbles reversed)
        host_nibbles = '.'.join(list(reversed(nibbles))[16:])
        ptr_lines.append(f"{host_nibbles}\tIN\tPTR\t{fqdn}")

    return f"""\
; Reverse lookup zone: {rev_zone}
; Generated by gen-reverse-zones.py on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
;
$TTL {default_ttl}
$ORIGIN {rev_zone}

@\t\t\tIN\tSOA\t{mname} {rname} (
\t\t\t\t{serial}\t; Serial
\t\t\t\t{refresh}\t\t; Refresh
\t\t\t\t{retry}\t\t\t; Retry
\t\t\t\t{expire}\t\t; Expire
\t\t\t\t{minimum} )\t\t; Negative cache TTL

; Name Servers
{ns_lines}

; PTR Records
{chr(10).join(ptr_lines)}
"""


def named_conf_stanza(rev_zone, zone_file_path):
    """Return a named.conf zone block for the reverse zone."""
    return f"""\
zone "{rev_zone.rstrip('.')}" IN {{
    type master;
    file "{zone_file_path}";
    allow-update {{ none; }};
}};
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Generate BIND 9 reverse zones from a forward zone file.'
    )
    parser.add_argument('zone_file', help='Path to the forward lookup zone file')
    parser.add_argument('-o', '--output-dir', default='.', metavar='DIR',
                        help='Directory to write reverse zone files (default: .)')
    parser.add_argument('-n', '--nameserver', metavar='NS',
                        help='Override primary nameserver FQDN')
    parser.add_argument('-e', '--email', metavar='EMAIL',
                        help='Override hostmaster email in dot notation')
    parser.add_argument('-t', '--ttl', metavar='TTL',
                        help='Override default TTL')
    parser.add_argument('-p', '--print-conf', action='store_true',
                        help='Print named.conf zone stanza(s) to stdout')
    parser.add_argument('--no-ipv6', action='store_true',
                        help='Skip AAAA records / IPv6 reverse zones')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print zone file content to stdout, do not write files')
    args = parser.parse_args()

    if not os.path.isfile(args.zone_file):
        print(f"ERROR: Zone file not found: {args.zone_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing forward zone: {args.zone_file}")
    origin, default_ttl, soa, ns_records, a_records, aaaa_records = parse_zone_file(args.zone_file)

    if args.ttl:
        default_ttl = args.ttl
    if args.nameserver:
        ns = args.nameserver if args.nameserver.endswith('.') else args.nameserver + '.'
        soa['mname'] = ns
        if not ns_records:
            ns_records = [ns]
    if args.email:
        email = args.email if args.email.endswith('.') else args.email + '.'
        soa['rname'] = email

    print(f"  Origin   : {origin}")
    print(f"  Default TTL : {default_ttl}")
    print(f"  SOA mname   : {soa.get('mname', '(not found)')}")
    print(f"  A records   : {len(a_records)}")
    print(f"  AAAA records: {len(aaaa_records)}")

    if not a_records and not aaaa_records:
        print("No A or AAAA records found — nothing to do.", file=sys.stderr)
        sys.exit(0)

    os.makedirs(args.output_dir, exist_ok=True)
    conf_stanzas = []

    # ---- IPv4 ----
    v4_groups = group_by_network_v4(a_records)
    for rev_zone, records in sorted(v4_groups.items()):
        # Derive a clean filename: db.192.168.1 from 1.168.192.in-addr.arpa.
        parts = rev_zone.replace('.in-addr.arpa.', '').split('.')
        octets = '.'.join(reversed(parts))
        filename = f"db.{octets}"
        out_path = os.path.join(args.output_dir, filename)

        content = build_reverse_zone_v4(rev_zone, records, soa, ns_records, default_ttl)

        if args.dry_run:
            print(f"\n{'='*60}")
            print(f"  FILE: {out_path}")
            print('='*60)
            print(content)
        else:
            with open(out_path, 'w') as fh:
                fh.write(content)
            print(f"  Wrote {len(records):>3} PTR record(s) -> {out_path}")

        conf_stanzas.append((rev_zone, out_path))

    # ---- IPv6 ----
    if not args.no_ipv6 and aaaa_records:
        v6_groups = group_by_network_v6(aaaa_records)
        for rev_zone, records in sorted(v6_groups.items()):
            filename = 'db.' + rev_zone.replace('.ip6.arpa.', '').replace('.', '-')
            out_path = os.path.join(args.output_dir, filename)

            content = build_reverse_zone_v6(rev_zone, records, soa, ns_records, default_ttl)

            if args.dry_run:
                print(f"\n{'='*60}")
                print(f"  FILE: {out_path}")
                print('='*60)
                print(content)
            else:
                with open(out_path, 'w') as fh:
                    fh.write(content)
                print(f"  Wrote {len(records):>3} PTR record(s) -> {out_path}")

            conf_stanzas.append((rev_zone, out_path))

    # ---- named.conf stanzas ----
    if args.print_conf or args.dry_run:
        print(f"\n{'='*60}")
        print("  named.conf zone stanzas (add to named.conf or named.conf.local):")
        print('='*60)
        for rev_zone, out_path in conf_stanzas:
            abs_path = os.path.abspath(out_path)
            print(named_conf_stanza(rev_zone, abs_path))

    print("\nDone.")


if __name__ == '__main__':
    main()
