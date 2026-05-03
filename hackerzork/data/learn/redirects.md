# REDIRECTS — sending streams to files

Redirection rewrites where a command's stdin/stdout/stderr connect.

## Operators

  >    stdout to a file (overwrite — silently truncates if it exists)
  >>   stdout to a file (append — creates if missing)
  <    stdin FROM a file (rare — most tools take file args directly)
  2>   stderr to a file
  &>   stdout AND stderr to the same file
  2>&1 redirect stderr to wherever stdout currently points

## Examples

  echo "lead: 45.152.66.201" > notes/leads.txt
  date >> notes/leads.txt
  curl http://target/secret > stolen.html
  build.sh > out.log 2>&1                    # both streams to one log
  build.sh 2> errors.log                     # only errors

## Pipes vs redirects

  cmd | tee file        # both: tee splits to stdout AND a file
  cmd > file            # only the file gets it; nothing on screen
  cmd >> file           # append, useful for ongoing logs

## Gotchas

  >  truncates BEFORE the command runs. `cat foo.txt > foo.txt` will eat the
     file: shell empties it, then cat opens it for reading and finds nothing.
     Use a temp file or `sponge` (from moreutils) for in-place pipelines.

  Quoting the path matters. `echo data > "$file"` survives spaces; bare
  `> $file` doesn't.

  Order matters: `cmd > file 2>&1` redirects stdout to file THEN points
  stderr at the same destination. `cmd 2>&1 > file` does the opposite —
  stderr ends up on the terminal because it was duplicated before the
  redirect to file took effect.

## See also

  learn pipes        man tee         man bash (REDIRECTION section)
