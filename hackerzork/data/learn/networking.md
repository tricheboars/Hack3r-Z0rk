# NETWORKING — the layers, fast

A working mental model in five layers.

## Layer 2 — the physical neighborhood

Ethernet / WiFi. Devices have MAC addresses (48-bit, like 00:1A:2B...).
Frames travel between MAC addresses on the same local segment. Switches
operate here. ARP maps MACs ↔ IPs on the local network.

## Layer 3 — IP

Every packet has a source and destination IP. Routers look at the dest IP
and forward based on routing tables. IPv4 addresses are 32 bits
(`10.13.37.1`); IPv6 are 128 (`2001:db8::1`). Subnet masks slice off the
"network" part: `10.0.0.0/24` means "the first 24 bits are the network".

## Layer 4 — TCP and UDP

  TCP   reliable, ordered stream. Three-way handshake (SYN/SYN-ACK/ACK).
        Connection-oriented. http, ssh, smtp.
  UDP   fire-and-forget datagrams. No handshake, no ordering. dns, ntp,
        most games and voice/video.

A connection is identified by a 4-tuple:
(src_ip, src_port, dst_ip, dst_port).

## Layer 7 — applications

HTTP, SSH, SMTP, IRC, DNS — protocols on top of TCP/UDP that define what
the bytes mean. Each has its own format and conventions.

## Useful tools

  ip a / ifconfig    your interfaces and addresses
  ip r / route -n    your routing table — where do packets go?
  ss -tunap          who has open connections (modern netstat)
  netstat -an        same, classic
  ping <host>        is anything replying to ICMP?
  traceroute <host>  path discovery via TTL trick
  dig / host         DNS resolution (better than `nslookup`)
  curl -v <url>      see the actual HTTP exchange
  tcpdump -i any port 80     watch traffic in real time

## DNS in 30 seconds

DNS turns names into IPs.

  ┌─ your /etc/hosts (tried first)
  ├─ your stub resolver (/etc/resolv.conf)
  ├─ your ISP's recursive resolver (or 1.1.1.1, 8.8.8.8, etc.)
  └─ authoritative servers (the .com server, then example.com's server)

Record types you'll meet: A (IPv4), AAAA (IPv6), CNAME (alias), MX (mail),
TXT (anything — used for SPF, DKIM, verification tokens).

`/etc/hosts` is consulted BEFORE DNS. An attacker who edits it can
redirect specific hostnames anywhere they like — and many people never
think to look there.

## Firewalls / NAT

Firewalls drop packets that don't match policy. NAT lets many private IPs
share one public IP by rewriting (src_ip:src_port) on outbound packets and
keeping a translation table for replies. Inbound connections from the
public side don't have a table entry → they're dropped, by accident or by
policy. That's why "behind NAT" is also (loosely) a firewall.

## See also

  learn port-scanning    learn ssh-keys    man tcpdump
