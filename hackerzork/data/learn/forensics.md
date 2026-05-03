# FORENSICS — what attackers leave behind

When something happens on a Unix system, it leaves traces. Most attackers
miss at least one. This page is a short tour of where to look.

## The timestamp trinity

Every file has three timestamps (ext4 has a fourth — birth time):

  atime  ACCESS time — last read
  mtime  MODIFY time — last content change
  ctime  CHANGE time — last metadata change (incl. perms, ownership)

If an attacker opens a file (atime), edits it (mtime), or chmods it
(ctime), the kernel updates these. They can be reset with `touch -t`,
but if the attacker isn't careful you'll see anomalies:

  - mtime IN THE PAST relative to ctime → metadata changed AFTER content
  - mtime EXACTLY at midnight 1970 → someone tried to wipe and screwed up
  - identical mtimes across many files → script-driven mass touch

`stat <file>` shows all three.

## Logs that matter

  /var/log/auth.log     authentication — every login attempt, sudo, ssh
  /var/log/syslog       kernel + system services
  /var/log/secure       (RHEL) auth log equivalent
  /var/log/wtmp         binary; query with `last` — historical logins
  /var/log/btmp         binary; query with `lastb` — failed login attempts
  ~/.bash_history       what the user typed in their shell

Logs an attacker DIDN'T modify usually contradict logs they did. Look for
gaps where activity should be present.

## Recoverable deletion

`rm` unlinks the directory entry. The data sits on disk until the blocks
are reused. Tools like `extundelete`, `photorec`, and `sleuthkit` walk the
raw filesystem for orphaned inodes.

In this game, `rm` sends entries to a recoverable trash by default —
`recover <path>` brings them back. An attacker rushing to clean up rarely
shreds (`shred -u`) — they `rm` and run.

## Process artifacts

Even after a process exits, traces remain:

  - lingering open files (lsof on a parent that inherited fds)
  - tmp files in /tmp, /var/tmp, /dev/shm
  - cron entries that respawn the malware
  - systemd unit files in unusual locations
  - LD_PRELOAD env vars or /etc/ld.so.preload entries
  - .bashrc / .profile additions that re-run on next login

## Persistence — the attacker's foothold

After initial access, attackers add a way back in:

  authorized_keys     extra ssh pubkey
  cron / at           timed re-launch
  systemd unit        service that runs the implant
  rc.local / init     ancient but still works
  webshell            tiny script in a web-served directory
  account creation    a new user (compare /etc/passwd against known list)

Reviewing these is the FIRST step after containment.

## In this game

The auth.log shows an unknown IP that SSHed in on March 15. The bash
history has a gap. Files in /var/log were truncated. /etc/hosts was
modified. exfil.py is in trash. Each of these is a real-world technique.

## See also

  man stat          man last          learn permissions
