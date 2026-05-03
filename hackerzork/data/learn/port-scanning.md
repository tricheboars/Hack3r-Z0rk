# PORT SCANNING — what nmap is actually doing

A port is a 16-bit number on a host (0–65535). When a process wants to
accept incoming TCP connections, it BINDS to a port. Other hosts reach it
via (ip, port). Port scanning is the act of asking "which ports on this
host have something listening?"

## TCP vs UDP

  TCP  connection-oriented, three-way handshake (SYN -> SYN/ACK -> ACK).
       Most "user-facing" services live here: ssh/22, http/80, https/443.
  UDP  connectionless. Send a packet, hope. DNS, NTP, many game protocols.
       Harder to scan reliably because there's no handshake to observe.

## SYN scan (-sS, default for nmap as root)

For each port:
  1. Send a TCP SYN.
  2. SYN/ACK back? Port is OPEN. Send a RST so the OS doesn't complete
     the handshake — many connection-tracking systems then never log it.
  3. RST back? Port is CLOSED — host is up, nothing listening.
  4. No reply? Port is FILTERED — a firewall dropped the packet.

This is "half-open" scanning. Stealthier than a full connect, but
modern IDS/IPS still catches the volume of SYNs.

## Connect scan (-sT, default without root)

Completes the full TCP handshake using the OS's connect() call. Always
logged (just like a normal client). Slower, noisier, but works without
raw socket privileges.

## Service-version scan (-sV)

After finding open ports, nmap speaks each protocol:

  port 22 open → send SSH greeting → parse banner → "OpenSSH 8.9"
  port 80 open → send HTTP HEAD    → parse Server  → "nginx 1.18.0"
  port 3306 open → MySQL handshake → "MySQL 5.7.38"

Now you have versions, which means you can look up CVEs.

## Other modes worth knowing

  -sU    UDP scan (slow — no handshake to observe)
  -sn    "ping sweep" — discover hosts without scanning ports
  -O     OS fingerprinting (analyze TCP/IP stack quirks)
  -A     "aggressive" — version + OS + scripts + traceroute
  -T0..5 timing — T0 paranoid (5 minutes between probes), T5 insane

## Stealth knobs

  --max-rate / --min-rate   throttle packet rate
  -f                       fragment packets
  -D <decoy,decoy,me>      spoof other source IPs alongside yours
  --spoof-mac              set a fake MAC

NONE of these defeat a well-tuned defender. They reduce the signal, they
don't eliminate it. Every scan in this game adds heat — that models what
a real defender's IDS would do.

## See also

  man nmap          learn cves        learn networking
