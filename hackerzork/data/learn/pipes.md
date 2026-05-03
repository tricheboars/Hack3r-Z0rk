# PIPES — composing tools with `|`

The pipe operator `|` connects one program's stdout to the next program's
stdin. This is the central trick of Unix: instead of one giant program that
does everything, you have many small ones, each doing one thing well, glued
together at the command line.

## The mental model

Every program has three streams:

  stdin   (file descriptor 0)   what the program reads
  stdout  (fd 1)                 normal output
  stderr  (fd 2)                 errors / diagnostics

A pipe `A | B` runs both programs simultaneously, with A's stdout wired to
B's stdin. Data flows through. stderr is NOT piped — error messages still
land on the terminal.

## Examples

  ps aux | grep sk_                  # processes whose lines match sk_
  cat /var/log/auth.log | grep FAIL  # failed-auth lines
  history | grep ssh                 # every ssh command you ran
  ls -la | wc -l                     # how many entries (incl. hidden)
  cat *.log | sort | uniq -c | sort -rn | head
                                     # classic top-N counter

## Why pipes win

- One tool changes? The rest of the pipeline is unaffected.
- Read each stage in plain English from left to right.
- Each tool can be tested standalone with sample input.
- Memory stays small — data streams, never fully materialized.

## Gotchas

- `grep` with no quotes lets the shell expand globs first. Always quote
  patterns that contain `*`, `?`, or `[`.
- A non-zero exit code in the middle of a pipeline doesn't fail the whole
  thing by default. Bash's `set -o pipefail` changes that.
- Pipes deadlock if a downstream stage stops reading before upstream stops
  writing — pick programs that consume their input.

## See also

  man grep          man find          man sed           man wc
  learn redirects   learn regex
