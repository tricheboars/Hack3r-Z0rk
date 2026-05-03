# REGEX — patterns for matching text

A regular expression is a tiny language for describing string patterns.
Once you know it, half the Unix toolbelt becomes one tool.

## The atoms

  .         any single character (except newline by default)
  \d        a digit (in extended/Perl regex)
  \w        word character — [A-Za-z0-9_]
  \s        whitespace
  ^         start of line
  $         end of line
  [abc]     any of a, b, c
  [^abc]    any character EXCEPT those
  [a-z]     range

## Quantifiers

  *         zero or more
  +         one or more
  ?         zero or one (optional)
  {n}       exactly n
  {n,m}     between n and m

## Groups and alternatives

  (foo)     group — capture for backreference
  foo|bar   either pattern
  \1 \2     backreferences to captured groups (in sed/awk/perl)

## Three flavors you'll meet

  BRE   "Basic" regex — grep default. ?+(){} need backslash escapes:
        grep '[A-Z]\+' file
  ERE   "Extended" regex — grep -E or egrep. Modern syntax:
        grep -E '[A-Z]+' file
  PCRE  Perl-compatible. grep -P. Adds \d \w lookarounds (?=...) etc.

When you see a regex that "doesn't work" in grep, check the flavor.

## Useful examples

  grep -E '^(ERROR|FATAL):'           lines starting with ERROR: or FATAL:
  grep -E '\b[A-Z]{3,}\b'             ALL-CAPS words 3+ chars
  grep -E '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'   IPv4-shaped strings
  grep -E 'CVE-[0-9]{4}-[0-9]+'       CVE references
  sed -E 's/  +/ /g'                  collapse multiple spaces

## Anchoring matters

`grep foo` matches any line containing "foo", including "foobar". Anchor
with `^foo`, `foo$`, or word boundaries `\bfoo\b` to be precise.

## Greedy vs lazy

`.*` is greedy — matches as much as possible. In PCRE, `.*?` is lazy —
matches as little as possible. In BRE/ERE there's no lazy form; use a
negated character class instead: `[^"]*`.

## See also

  man grep          man sed           man re_format     learn pipes
