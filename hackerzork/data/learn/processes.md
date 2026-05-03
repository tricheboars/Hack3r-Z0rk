# PROCESSES — what's actually running

A process is a running instance of a program. The kernel tracks every one.

## Anatomy

  PID    process id (integer, unique while running)
  PPID   parent process id — every process has a parent except init (PID 1)
  UID    the user the process runs AS (matters for permissions, kill)
  CMD    the executable + args (you see what was invoked, not always full)
  STATE  R running, S sleeping, D uninterruptible (often disk I/O), Z zombie
  TIME   total CPU time consumed
  RSS    resident memory in pages (×4KiB on most systems)

## Listing them

  ps aux             BSD form — USER PID %CPU %MEM ... COMMAND
  ps -ef             System V form — UID PID PPID ... CMD
  pstree             tree of parent/child relationships
  htop / top         live updating, interactive
  pgrep <pattern>    just the PIDs matching
  pidof <name>       PIDs of an exact-name process

The two ps forms exist because Unix forked into BSD and System V camps in
the 80s and the conventions never reconverged. Both are everywhere.

## Lifecycle

  fork()      create a copy of the current process (returns twice — child
              gets 0, parent gets the child's PID). Old-school Unix way.
  exec()      replace the current process image with another program.
              fork+exec together is how `bash` runs every command.
  wait()      parent reaps the child, gets its exit code.
  exit()      child terminates, becomes a ZOMBIE until parent waits.

If a parent dies before its child, the child is REPARENTED to PID 1 (init
or systemd), which reaps it. Orphaned-then-reparented processes are how
backgrounded services often look in `ps`.

## Signals (man 7 signal)

A process can be sent SIGNALS — async notifications.

  SIGTERM (15)   please stop. Process can trap and clean up.
  SIGKILL (9)    forced. Kernel kills it, no trap, no cleanup.
  SIGINT  (2)    Ctrl+C from the keyboard.
  SIGHUP  (1)    historically "terminal hung up". Now: reload config.
  SIGSTOP/CONT   pause and resume (job control).

`kill -9` exists but use `-15` first; the process can flush buffers and
unlock files. Skip the polite version only when something is wedged.

## Suspicious-process patterns

  - Wrong USER for the role (a `cat` running as root for hours?)
  - Parent is gone (PPID 1 for things that shouldn't be daemonized)
  - High CPU on something idle by name
  - Names that LOOK normal but live in unexpected paths
        /usr/bin/ssh    legitimate
        /tmp/ssh        very much not
  - Recurring respawn — a process you killed comes right back. There's a
    PARENT or a cron job re-launching it. Find that, not the symptom.

## See also

  man ps            man kill          man 7 signal      learn signals
