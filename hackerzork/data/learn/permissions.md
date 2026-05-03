# PERMISSIONS — Unix mode bits

Every file and directory has a MODE: who can do what to it.

## The rwx triplets

`ls -l` shows mode as 10 characters:

    -rwxr-xr--   1 user staff  4096 Mar 15 02:31 exfil.py
    │└─┬─┘└─┬─┘└─┬─┘
    │  │    │    └── OTHER  (everyone else)
    │  │    └─────── GROUP  (members of the file's group)
    │  └──────────── OWNER  (the user who owns the file)
    └─────────────── TYPE   (- file, d dir, l symlink)

Each triplet is read / write / execute, in that order. A `-` means denied.

## Octal form

Each rwx triplet is a 3-bit number: r=4, w=2, x=1. So:

    rwx = 7   r-x = 5   r-- = 4   --- = 0

A full mode is three digits (owner / group / other):

    700  rwx ---  ---   only you can do anything
    755  rwx r-x r-x   common for executables and dirs
    644  rw- r-- r--   common for regular files
    600  rw- --- ---   secrets (private keys, .bash_history)
    777  rwx rwx rwx   "I have no idea what I'm doing"

## On directories

  r  list entries (ls works)
  w  create/rename/delete entries (NOT 'edit' — that's the file's mode)
  x  traverse INTO the dir (cd works, can resolve paths through it)

So a 711 dir lets others `cd` into it but not `ls` it — they can access a
specific path if they already know it. Useful trick.

## Symbolic form (chmod)

  chmod u+x script.sh        # add execute for owner
  chmod g-w report.pdf       # remove write for group
  chmod o= secret            # zero out 'other' permissions
  chmod a+r README           # all (= u+g+o) get read

## Special bits (less common)

  setuid (s in user's x slot)   binary runs as the file's OWNER, not the
                                caller. /usr/bin/sudo has this.
  setgid (s in group's x slot)  binary runs as group; on dirs, new files
                                inherit the dir's group.
  sticky (t in other's x slot)  on a dir, only the owner of an entry can
                                delete it (think /tmp).

## Why this matters here

ssh REFUSES to use a private key that is group/world-readable. If your
~/.ssh/id_ed25519 is mode 644, no key auth — only password.

`chmod 700 ~/.ssh` and `chmod 600 ~/.ssh/id_ed25519` is the canonical
lockdown.

## See also

  man chmod          man umask         learn ssh-keys
