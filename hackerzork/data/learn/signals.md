# SIGNALS — async messages between processes

A signal is a small, async notification the kernel delivers to a process.
Think of them as numbered "interrupts" with default behaviors a process
can override.

## The signals you'll actually use

  SIGHUP   1  reload config (historically: terminal hung up)
  SIGINT   2  Ctrl+C
  SIGQUIT  3  Ctrl+\ (also dumps core)
  SIGKILL  9  forced kill — cannot be trapped, cannot be ignored
  SIGTERM 15  polite stop — DEFAULT signal for `kill`
  SIGSTOP 19  pause (also can't be trapped)
  SIGCONT 18  resume after STOP
  SIGUSR1 10  application-defined, often "rotate logs"
  SIGUSR2 12  application-defined, often "reopen files"

Full list: `kill -l` or `man 7 signal`.

## Sending signals

  kill PID            sends SIGTERM (15)
  kill -9 PID         sends SIGKILL — escalate when TERM is ignored
  kill -HUP $(pidof nginx)    name-based with pgrep/pidof
  pkill -HUP nginx    by name, no pid lookup
  pkill -9 -u alice   every process of user alice

## Trapping signals (in shell scripts)

  trap 'cleanup' EXIT INT TERM
  trap 'reload_config' HUP

The trap handler runs when the named signal arrives. Use it for cleanup
on normal exit AND on Ctrl+C.

## What CAN'T be trapped

SIGKILL and SIGSTOP. By design. The kernel handles them so a runaway
process can always be stopped. If a process won't die from SIGKILL, it's
stuck in the kernel (uninterruptible D-state, usually disk I/O).

## In this game

`kill -9 sk_*` sends SIGKILL to a SkyNet observation process. The
persistence module catches the death event from the parent and respawns
the child. Net effect: process is back in seconds, plus heat is added.
Killing isn't the answer — finding the parent is.

## See also

  man 7 signal      man kill          learn processes
