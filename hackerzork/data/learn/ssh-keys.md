# SSH KEYS — public-key auth in 5 minutes

ssh supports two main auth modes: PASSWORD and PUBLIC KEY. Public-key auth
is faster, scriptable, and immune to password phishing.

## How it works

You generate a KEYPAIR:

    ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519
    → produces id_ed25519       (PRIVATE — never share, mode 600)
              id_ed25519.pub   (PUBLIC  — copy to servers)

You append the .pub line to the server's
`~/<user>/.ssh/authorized_keys` file. Now when you ssh:

  1. Server sends a random challenge.
  2. Your client signs it with the private key.
  3. Server verifies the signature against the public key in
     authorized_keys.

The private key never leaves your machine. The signature can't be
replayed (challenges are random). No password crosses the wire.

## Algorithms (modern → legacy)

  ed25519   small, fast, modern. Default for new keys.
  rsa-4096  ubiquitous, slower, larger. Still fine.
  ecdsa     short keys, but the NIST curves are politically suspect.
  dsa       DEAD. Don't generate, refuse to accept.

## Required file modes

  ~/.ssh                  700  drwx------
  ~/.ssh/id_ed25519       600  -rw-------    private — only you
  ~/.ssh/id_ed25519.pub   644  -rw-r--r--    public — share freely
  ~/.ssh/authorized_keys  600  -rw-------    server-side, trusted keys
  ~/.ssh/known_hosts      600  -rw-------    server fingerprints (pinned)

ssh REFUSES private keys that are group/world-readable. If auth fails for
"no obvious reason", check the modes first.

## known_hosts and TOFU

The first time you connect to a server, ssh prints:

    The authenticity of host '10.13.37.1' can't be established.
    ED25519 key fingerprint is SHA256:abcd...
    Are you sure you want to continue connecting (yes/no)?

This is TOFU — Trust On First Use. You accept, the fingerprint goes into
known_hosts. On every future connection, ssh checks the host key matches.
If it doesn't, ssh refuses with REMOTE HOST IDENTIFICATION HAS CHANGED —
that's the MITM warning. Verify out-of-band before clearing the entry.

## Backdoor pattern to know

After compromising a host, an attacker often:

  1. Generates a fresh keypair on their machine.
  2. Appends the .pub to the victim's authorized_keys.
  3. Disconnects, comes back later via key auth.

This survives password changes. After any incident, AUDIT
authorized_keys on every account. Look for keys you didn't put there.

## See also

  man ssh           man ssh-keygen    learn permissions     learn encryption
