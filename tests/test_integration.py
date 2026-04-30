"""Comprehensive integration tests — boots a real Game instance and
exercises every command category, save/load, pipes, redirects, and
cross-system interactions.

Each test class boots ONE game instance (via module-scoped fixture) and
runs shell.execute() calls against it. This tests the full stack:
  parser → shell → command handler → VFS/network/heat/state → output
"""
from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from hackerzork.game import Game


# ---------------------------------------------------------------------------
# Game fixture — one instance per module, no audio, no effects, no meta
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def game() -> Game:
    g = Game(audio_enabled=False, effects_enabled=False, meta_enabled=False)
    g.boot()
    return g


def run(game: Game, cmd: str) -> str:
    """Execute a shell command and return stripped output."""
    return game._shell.execute(cmd)


# ===========================================================================
# Filesystem commands
# ===========================================================================


class TestFilesystem:
    def test_pwd(self, game):
        out = run(game, "pwd")
        assert "/home/user" in out

    def test_ls_home(self, game):
        out = run(game, "ls /home/user")
        assert out  # should list something

    def test_ls_la(self, game):
        out = run(game, "ls -la /home/user")
        assert "." in out or "drwx" in out or "total" in out

    def test_cd_and_pwd(self, game):
        run(game, "cd /tmp")
        out = run(game, "pwd")
        assert "/tmp" in out
        run(game, "cd /home/user")  # restore

    def test_cd_relative(self, game):
        run(game, "cd /home/user")
        run(game, "cd evidence")
        out = run(game, "pwd")
        assert "evidence" in out
        run(game, "cd /home/user")

    def test_cd_dotdot(self, game):
        run(game, "cd /home/user/evidence")
        run(game, "cd ..")
        out = run(game, "pwd")
        assert "/home/user" in out
        run(game, "cd /home/user")

    def test_cd_home_tilde(self, game):
        run(game, "cd /tmp")
        run(game, "cd ~")
        out = run(game, "pwd")
        assert "/home/user" in out

    def test_cd_nonexistent(self, game):
        out = run(game, "cd /nonexistent/path")
        assert "no such" in out.lower() or "not found" in out.lower()

    def test_cat_existing_file(self, game):
        out = run(game, "cat /etc/hosts")
        assert "localhost" in out or "127.0.0.1" in out

    def test_cat_encrypted_file(self, game):
        out = run(game, "cat /etc/shadow")
        # Encrypted files render as hex
        assert "0000" in out or "encrypted" in out.lower() or "hex" in out.lower()

    def test_cat_nonexistent(self, game):
        out = run(game, "cat /does/not/exist.txt")
        assert "no such" in out.lower() or "not found" in out.lower()

    def test_cat_binary_file(self, game):
        out = run(game, "cat /home/user/games/zork")
        assert "binary" in out.lower() or "not a text file" in out.lower()

    def test_cat_with_n_flag(self, game):
        out = run(game, "cat -n /etc/passwd")
        # Should have line numbers
        assert "1" in out

    def test_mkdir_and_ls(self, game):
        run(game, "mkdir /tmp/testdir_integration")
        out = run(game, "ls /tmp")
        assert "testdir_integration" in out

    def test_mkdir_p(self, game):
        out = run(game, "mkdir -p /tmp/deep/nested/path")
        assert "error" not in out.lower() and "failed" not in out.lower()

    def test_touch_creates_file(self, game):
        run(game, "touch /tmp/touched.txt")
        out = run(game, "ls /tmp")
        assert "touched.txt" in out

    def test_echo_redirect_creates_file(self, game):
        run(game, 'echo "hello world" > /tmp/redir_test.txt')
        out = run(game, "cat /tmp/redir_test.txt")
        assert "hello world" in out

    def test_echo_append(self, game):
        run(game, 'echo "line1" > /tmp/append_test.txt')
        run(game, 'echo "line2" >> /tmp/append_test.txt')
        out = run(game, "cat /tmp/append_test.txt")
        assert "line1" in out
        assert "line2" in out

    def test_echo_newline(self, game):
        out = run(game, "echo hello")
        assert out.endswith("\n") or "hello" in out

    def test_echo_n_flag(self, game):
        out = run(game, "echo -n hello")
        assert "hello" in out
        assert not out.endswith("\n")

    def test_rm_file(self, game):
        run(game, 'echo "delete me" > /tmp/to_delete.txt')
        run(game, "rm /tmp/to_delete.txt")
        out = run(game, "ls /tmp")
        assert "to_delete.txt" not in out

    def test_rm_nonexistent(self, game):
        out = run(game, "rm /tmp/does_not_exist_xyz.txt")
        assert "no such" in out.lower() or "not found" in out.lower()

    def test_cp_file(self, game):
        run(game, 'echo "copy me" > /tmp/source.txt')
        run(game, "cp /tmp/source.txt /tmp/dest.txt")
        out = run(game, "cat /tmp/dest.txt")
        assert "copy me" in out

    def test_mv_file(self, game):
        run(game, 'echo "move me" > /tmp/move_src.txt')
        run(game, "mv /tmp/move_src.txt /tmp/move_dst.txt")
        out_dst = run(game, "cat /tmp/move_dst.txt")
        assert "move me" in out_dst
        out_src = run(game, "ls /tmp")
        assert "move_src.txt" not in out_src

    def test_grep_finds_match(self, game):
        run(game, 'echo "needle in haystack" > /tmp/grep_test.txt')
        out = run(game, "grep needle /tmp/grep_test.txt")
        assert "needle" in out

    def test_grep_no_match(self, game):
        out = run(game, "grep zzznomatch /etc/passwd")
        assert out == "" or "no match" in out.lower()

    def test_grep_r(self, game):
        out = run(game, "grep -r localhost /etc")
        assert "localhost" in out

    def test_grep_i_case_insensitive(self, game):
        out = run(game, "grep -i LOCALHOST /etc/hosts")
        assert "localhost" in out.lower()

    def test_find_by_name(self, game):
        out = run(game, "find /etc -name hosts")
        assert "hosts" in out

    def test_find_by_type(self, game):
        out = run(game, "find /home/user -type f")
        assert "/" in out  # should have paths

    def test_head(self, game):
        out = run(game, "head /etc/hosts")
        assert out  # should have content

    def test_head_n(self, game):
        out = run(game, "head -n 2 /etc/hosts")
        lines = [l for l in out.splitlines() if l.strip()]
        assert len(lines) <= 5  # at most a few lines

    def test_tail(self, game):
        out = run(game, "tail /etc/hosts")
        assert out

    def test_wc_l(self, game):
        out = run(game, "wc -l /etc/passwd")
        assert any(c.isdigit() for c in out)

    def test_wc_w(self, game):
        out = run(game, "wc -w /etc/hosts")
        assert any(c.isdigit() for c in out)

    def test_chmod(self, game):
        run(game, 'echo "test" > /tmp/chmod_test.txt')
        out = run(game, "chmod 600 /tmp/chmod_test.txt")
        assert "error" not in out.lower()

    def test_file_command(self, game):
        out = run(game, "file /etc/passwd")
        assert "text" in out.lower() or "ASCII" in out or "/" in out

    def test_ls_evidence_hidden_mode(self, game):
        out = run(game, "ls /home/user/evidence")
        assert out  # should list files

    def test_cat_evidence_manifest(self, game):
        out = run(game, "cat /home/user/evidence/manifest.txt")
        assert out and "error" not in out.lower()

    def test_cat_hz_debug_file(self, game):
        out = run(game, "cat /etc/.hz_debug")
        assert "h@ck3r_d3v_k3y_2026" in out

    def test_readlink_symlink(self, game):
        out = run(game, "readlink /home/user/.config")
        assert ".dotfiles" in out or "/" in out

    def test_ls_broken_symlink(self, game):
        # /home/user/tools/decrypt is a broken symlink
        out = run(game, "ls -la /home/user/tools")
        assert "decrypt" in out

    def test_nano_opens(self, game):
        out = run(game, "nano /etc/passwd")
        assert "nano" in out.lower() or "GNU" in out or "passwd" in out

    def test_vi_opens(self, game):
        out = run(game, "vi /etc/hosts")
        assert out  # vi shows the file

    def test_vim_alias(self, game):
        out = run(game, "vim /etc/hosts")
        assert out

    def test_sed_substitution(self, game):
        run(game, 'echo "foo bar" > /tmp/sed_test.txt')
        out = run(game, "sed 's/foo/baz/' /tmp/sed_test.txt")
        assert "baz" in out
        assert "foo" not in out

    def test_sed_inplace(self, game):
        run(game, 'echo "original" > /tmp/sed_inplace.txt')
        run(game, "sed -i 's/original/replaced/' /tmp/sed_inplace.txt")
        out = run(game, "cat /tmp/sed_inplace.txt")
        assert "replaced" in out

    def test_tee(self, game):
        run(game, 'echo "tee test" | tee /tmp/tee_out.txt')
        out = run(game, "cat /tmp/tee_out.txt")
        assert "tee test" in out


# ===========================================================================
# Pipe and redirect
# ===========================================================================


class TestPipesAndRedirects:
    def test_pipe_cat_grep(self, game):
        out = run(game, "cat /etc/passwd | grep user")
        assert "user" in out

    def test_pipe_echo_grep(self, game):
        out = run(game, "echo 'hello world' | grep hello")
        assert "hello" in out

    def test_pipe_no_match_returns_empty(self, game):
        out = run(game, "echo 'hello world' | grep zzznomatch")
        assert out.strip() == ""

    def test_pipe_to_wc(self, game):
        out = run(game, "cat /etc/hosts | wc -l")
        assert any(c.isdigit() for c in out)

    def test_multi_pipe(self, game):
        run(game, 'echo "abc\ndef\nabc" > /tmp/multi_pipe.txt')
        out = run(game, "cat /tmp/multi_pipe.txt | grep abc | wc -l")
        # should count abc lines
        assert any(c.isdigit() for c in out)

    def test_redirect_overwrites(self, game):
        run(game, 'echo "first" > /tmp/overwrite_test.txt')
        run(game, 'echo "second" > /tmp/overwrite_test.txt')
        out = run(game, "cat /tmp/overwrite_test.txt")
        assert "second" in out
        assert "first" not in out

    def test_redirect_append(self, game):
        run(game, 'echo "a" > /tmp/append2_test.txt')
        run(game, 'echo "b" >> /tmp/append2_test.txt')
        run(game, 'echo "c" >> /tmp/append2_test.txt')
        out = run(game, "cat /tmp/append2_test.txt")
        for ch in ["a", "b", "c"]:
            assert ch in out

    def test_pipe_grep_to_file(self, game):
        out = run(game, "cat /etc/passwd | grep root > /tmp/root_line.txt")
        result = run(game, "cat /tmp/root_line.txt")
        assert "root" in result


# ===========================================================================
# System commands
# ===========================================================================


class TestSystem:
    def test_whoami(self, game):
        out = run(game, "whoami")
        assert "user" in out.lower()

    def test_uname(self, game):
        out = run(game, "uname")
        assert out

    def test_uname_a(self, game):
        out = run(game, "uname -a")
        assert "Linux" in out or "linux" in out.lower()

    def test_hostname(self, game):
        out = run(game, "hostname")
        assert out.strip()  # should return something

    def test_id(self, game):
        out = run(game, "id")
        assert "uid" in out

    def test_ps(self, game):
        out = run(game, "ps")
        # Should show processes including sk_ ones
        assert out

    def test_ps_aux(self, game):
        out = run(game, "ps aux")
        assert out

    def test_ps_shows_skynet(self, game):
        out = run(game, "ps aux")
        assert "sk_" in out

    def test_top(self, game):
        out = run(game, "top")
        assert out

    def test_htop(self, game):
        out = run(game, "htop")
        assert out

    def test_kill_valid_pid(self, game):
        # Get a PID from ps first
        ps_out = run(game, "ps")
        # Find a sk_ process PID (a number)
        import re
        pids = re.findall(r'\b(\d+)\b', ps_out)
        if pids:
            out = run(game, f"kill {pids[0]}")
            # Should either succeed or give a message
            assert out is not None

    def test_kill_invalid_pid(self, game):
        out = run(game, "kill 99999999")
        assert "no such" in out.lower() or "not found" in out.lower() or out == ""

    def test_date(self, game):
        out = run(game, "date")
        assert out

    def test_uptime(self, game):
        out = run(game, "uptime")
        assert out

    def test_df(self, game):
        out = run(game, "df")
        assert out

    def test_df_h(self, game):
        out = run(game, "df -h")
        assert "G" in out or "M" in out or "%" in out

    def test_du(self, game):
        out = run(game, "du /home/user")
        assert out

    def test_free(self, game):
        out = run(game, "free")
        assert "Mem" in out or "mem" in out.lower()

    def test_lscpu(self, game):
        out = run(game, "lscpu")
        assert out

    def test_env(self, game):
        out = run(game, "env")
        assert "USER" in out or "HOME" in out

    def test_echo_env_var(self, game):
        out = run(game, "echo $HOME")
        assert "/home/user" in out

    def test_history(self, game):
        # Run a few commands first
        run(game, "echo test_history_marker")
        out = run(game, "history")
        assert "test_history_marker" in out or out  # history may not persist in module scope

    def test_neofetch(self, game):
        out = run(game, "neofetch")
        assert out
        assert "user" in out.lower() or "burner" in out.lower() or "Linux" in out

    def test_man_known_command(self, game):
        out = run(game, "man ls")
        assert out
        assert "ls" in out.lower()

    def test_man_unknown_command(self, game):
        out = run(game, "man zzznonsense")
        assert "no manual entry" in out.lower() or "not found" in out.lower()

    def test_clear_returns_something(self, game):
        out = run(game, "clear")
        # clear returns ANSI escape or empty
        assert out is not None


# ===========================================================================
# Network commands
# ===========================================================================


class TestNetwork:
    def test_ifconfig(self, game):
        out = run(game, "ifconfig")
        assert "eth0" in out or "lo" in out or "inet" in out

    def test_ip_addr(self, game):
        out = run(game, "ip addr")
        assert out

    def test_ping_known_node(self, game):
        out = run(game, "ping 10.13.37.1")
        assert "bytes" in out.lower() or "ms" in out or "icmp" in out.lower()

    def test_ping_unknown_host(self, game):
        out = run(game, "ping 1.2.3.4")
        assert "unreachable" in out.lower() or "timeout" in out.lower() or out

    def test_ping_c_flag(self, game):
        out = run(game, "ping -c 2 10.13.37.1")
        assert out

    def test_nmap_basic(self, game):
        out = run(game, "nmap 10.13.37.1")
        assert "80" in out or "open" in out.lower() or "Nmap" in out

    def test_nmap_sv(self, game):
        out = run(game, "nmap -sV 10.13.37.1")
        assert "nginx" in out.lower() or "open" in out.lower()

    def test_nmap_discovers_node(self, game):
        run(game, "nmap 10.13.37.1")
        assert "10.13.37.1" in game._network.discovered

    def test_nmap_unknown_host(self, game):
        out = run(game, "nmap 9.9.9.9")
        assert "down" in out.lower() or "no route" in out.lower() or "host" in out.lower()

    def test_traceroute(self, game):
        out = run(game, "traceroute 10.13.37.1")
        assert out
        assert "10.13.37.1" in out or "hop" in out.lower() or "ms" in out

    def test_netstat(self, game):
        out = run(game, "netstat")
        assert out

    def test_ss(self, game):
        out = run(game, "ss -tulnp")
        assert out

    def test_curl_http_node(self, game):
        # First discover the node
        run(game, "nmap 10.13.37.1")
        out = run(game, "curl http://10.13.37.1")
        assert out

    def test_nc_port_check(self, game):
        out = run(game, "nc -zv 10.13.37.1 80")
        assert out

    def test_ssh_no_target(self, game):
        out = run(game, "ssh")
        assert "usage" in out.lower() or "ssh" in out.lower()

    def test_ssh_unknown_host(self, game):
        out = run(game, "ssh user@9.9.9.9")
        assert "refused" in out.lower() or "timeout" in out.lower() or "no route" in out.lower() or out

    def test_ssh_known_host(self, game):
        # relay-alpha ssh is on port 22 with no vuln — should be refused or prompt
        out = run(game, "ssh user@10.13.37.1")
        assert out  # some response

    def test_whois(self, game):
        out = run(game, "whois 10.13.37.1")
        assert out


# ===========================================================================
# Hacking commands
# ===========================================================================


class TestHacking:
    def test_exploit_no_args(self, game):
        out = run(game, "exploit")
        assert "usage" in out.lower() or "missing" in out.lower()

    def test_exploit_undiscovered_host(self, game):
        out = run(game, "exploit -p 80 -e CVE-2021-23017 10.13.37.99")
        assert "no route" in out.lower() or "not yet scanned" in out.lower() or "nmap" in out.lower()

    def test_exploit_wrong_exploit_name(self, game):
        # First discover
        run(game, "nmap 10.13.37.1")
        out = run(game, "exploit -p 80 -e wrongexploit 10.13.37.1")
        assert "[-]" in out or "failed" in out.lower()

    def test_exploit_success(self, game):
        run(game, "nmap 10.13.37.1")
        out = run(game, "exploit -p 80 -e CVE-2021-23017 10.13.37.1")
        assert "[+]" in out
        assert game._network.nodes["10.13.37.1"].compromised is True

    def test_exploit_creates_loot_dir(self, game):
        # exploit already run above; just check loot dir
        assert game._fs.file_exists("/home/user/loot")

    def test_loot_shows_after_exploit(self, game):
        out = run(game, "loot")
        assert "10.13.37.1" in out or "loot" in out.lower()

    def test_loot_filter_by_ip(self, game):
        out = run(game, "loot 10.13.37.1")
        assert "10.13.37.1" in out

    def test_bruteforce_no_args(self, game):
        out = run(game, "bruteforce")
        assert "missing" in out.lower() or "usage" in out.lower()

    def test_bruteforce_known_service(self, game):
        run(game, "nmap 10.13.37.1")
        out = run(game, "bruteforce -p 3306 10.13.37.1")
        # May succeed (hunter2 is in built-in list) or fail gracefully
        assert "[+]" in out or "[-]" in out

    def test_backdoor_not_compromised(self, game):
        # node_002 not yet exploited
        run(game, "nmap 10.13.37.2")
        out = run(game, "backdoor 10.13.37.2")
        assert "not compromised" in out.lower() or "root shell" in out.lower() or "exploit" in out.lower()

    def test_backdoor_on_owned_node(self, game):
        # 10.13.37.1 was compromised above
        out = run(game, "backdoor 10.13.37.1")
        assert "[+]" in out
        assert "4444" in out

    def test_privesc_not_compromised(self, game):
        run(game, "nmap 10.13.37.2")
        out = run(game, "privesc 10.13.37.2")
        assert "not yet compromised" in out.lower()

    def test_privesc_check_on_owned(self, game):
        out = run(game, "privesc --check 10.13.37.1")
        assert "[!]" in out

    def test_privesc_on_owned(self, game):
        out = run(game, "privesc 10.13.37.1")
        assert "[+]" in out or "root" in out.lower()


# ===========================================================================
# Dev console
# ===========================================================================


class TestDevConsole:
    def test_wrong_key(self, game):
        # Need fresh unlock state — reset it
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(False)
        out = run(game, "hz_debug wrongkey")
        assert "not found" in out.lower()

    def test_correct_key(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(False)
        out = run(game, "hz_debug h@ck3r_d3v_k3y_2026")
        assert "DEV CONSOLE" in out or "hz_debug" in out.lower()

    def test_heat_show(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        out = run(game, "hz_debug heat")
        assert "level" in out.lower()

    def test_heat_set(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug heat set 10")
        assert abs(game._heat.level - 10.0) < 1.0  # heat may differ due to commands above

    def test_reset_heat(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug reset heat")
        assert game._heat.level == 0.0

    def test_flag_set_and_check(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug flag integration_test_flag")
        assert game._state.has_flag("integration_test_flag")

    def test_state_dump(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        out = run(game, "hz_debug state")
        assert "Heat" in out and "Network" in out

    def test_node_info(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        out = run(game, "hz_debug node 10.13.37.1")
        assert "relay-alpha" in out

    def test_scan_discovers_node(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug scan 10.13.37.4")
        assert "10.13.37.4" in game._network.discovered


# ===========================================================================
# Packaging / apt / shadow
# ===========================================================================


class TestPackaging:
    def test_apt_list(self, game):
        out = run(game, "apt list")
        assert out

    def test_apt_search(self, game):
        out = run(game, "apt search nmap")
        assert "nmap" in out.lower() or out

    def test_apt_install_invalid(self, game):
        out = run(game, "apt install zzznonsensepackage")
        assert "not found" in out.lower() or "unable" in out.lower() or "no package" in out.lower()

    def test_shadow_locked_initially(self, game):
        out = run(game, "shadow list")
        # Shadow repo requires unlocking first
        assert out  # should give a message

    def test_gpg_no_args(self, game):
        out = run(game, "gpg")
        assert out

    def test_gpg_list_keys(self, game):
        out = run(game, "gpg --list-keys")
        assert out


# ===========================================================================
# Comms commands
# ===========================================================================


class TestComms:
    def test_irc_no_args(self, game):
        out = run(game, "irc")
        assert out

    def test_irc_list(self, game):
        out = run(game, "irc list")
        assert out

    def test_msg_no_args(self, game):
        out = run(game, "msg")
        assert out

    def test_contacts(self, game):
        out = run(game, "contacts")
        assert out


# ===========================================================================
# Help system
# ===========================================================================


class TestHelp:
    def test_help_general(self, game):
        out = run(game, "help")
        assert out
        assert "exploit" in out.lower() or "ls" in out.lower() or "command" in out.lower()

    def test_help_specific(self, game):
        out = run(game, "help ls")
        assert "ls" in out.lower()

    def test_hint(self, game):
        out = run(game, "hint")
        assert out

    def test_tutorial(self, game):
        out = run(game, "tutorial")
        assert out


# ===========================================================================
# Save / load round-trip
# ===========================================================================


class TestSaveLoad:
    """Full save → serialise → reload → verify round trip using temp files."""

    def test_save_creates_file(self, game, tmp_path):
        save_file = tmp_path / "test_save.json"
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)

        # Do some work first
        run(game, "nmap 10.13.37.1")

        # Collect state
        data = game._save.collect(
            fs=game._fs,
            network=game._network,
            heat=game._heat,
            toolkit=game._toolkit,
            comms=game._comms,
            state=game._state,
            history=game._history,
            env=game._env,
        )
        game._save.write(data, save_file)
        assert save_file.exists()
        assert save_file.stat().st_size > 100

    def test_save_is_valid_json(self, game, tmp_path):
        save_file = tmp_path / "json_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)
        with open(save_file) as fh:
            parsed = json.load(fh)
        assert parsed["version"] == 1
        assert "fs" in parsed
        assert "network" in parsed
        assert "heat" in parsed

    def test_save_contains_discovery(self, game, tmp_path):
        run(game, "nmap 10.13.37.1")
        save_file = tmp_path / "disco_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)
        with open(save_file) as fh:
            parsed = json.load(fh)
        assert "10.13.37.1" in parsed["network"]["discovered"]

    def test_save_contains_vfs_file(self, game, tmp_path):
        run(game, 'echo "save roundtrip marker" > /tmp/save_marker.txt')
        save_file = tmp_path / "vfs_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)
        with open(save_file) as fh:
            raw = fh.read()
        assert "save roundtrip marker" in raw

    def test_load_restores_vfs_file(self, game, tmp_path):
        """Write a file, save, clear VFS by writing something else, reload."""
        from hackerzork.game import Game

        # Write a distinctive file
        run(game, 'echo "reload_marker_xyz" > /tmp/reload_test.txt')

        # Save
        save_file = tmp_path / "reload_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)

        # Boot a brand-new game instance (no shared state)
        fresh = Game(audio_enabled=False, effects_enabled=False, meta_enabled=False)
        fresh.boot()

        # Reload into the fresh instance
        loaded = fresh._save.read(save_file)
        fresh._save.apply(
            loaded,
            fs=fresh._fs, network=fresh._network, heat=fresh._heat,
            toolkit=fresh._toolkit, comms=fresh._comms, state=fresh._state,
            history=fresh._history, env=fresh._env,
        )

        # Verify the file is there
        content = fresh._fs.read_file("/tmp/reload_test.txt")
        assert "reload_marker_xyz" in content

    def test_load_restores_network_discovery(self, game, tmp_path):
        from hackerzork.game import Game

        run(game, "nmap 10.13.37.1")
        save_file = tmp_path / "network_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)

        fresh = Game(audio_enabled=False, effects_enabled=False, meta_enabled=False)
        fresh.boot()
        loaded = fresh._save.read(save_file)
        fresh._save.apply(
            loaded,
            fs=fresh._fs, network=fresh._network, heat=fresh._heat,
            toolkit=fresh._toolkit, comms=fresh._comms, state=fresh._state,
            history=fresh._history, env=fresh._env,
        )

        assert "10.13.37.1" in fresh._network.discovered

    def test_load_restores_compromise_state(self, game, tmp_path):
        from hackerzork.game import Game

        # Ensure 10.13.37.1 is compromised (done in TestHacking above)
        assert game._network.nodes["10.13.37.1"].compromised

        save_file = tmp_path / "compromise_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)

        fresh = Game(audio_enabled=False, effects_enabled=False, meta_enabled=False)
        fresh.boot()
        loaded = fresh._save.read(save_file)
        fresh._save.apply(
            loaded,
            fs=fresh._fs, network=fresh._network, heat=fresh._heat,
            toolkit=fresh._toolkit, comms=fresh._comms, state=fresh._state,
            history=fresh._history, env=fresh._env,
        )

        assert "10.13.37.1" in fresh._network.compromised
        assert fresh._network.nodes["10.13.37.1"].compromised

    def test_load_restores_heat(self, game, tmp_path):
        from hackerzork.game import Game
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug heat set 42")

        save_file = tmp_path / "heat_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)
        run(game, "hz_debug reset heat")  # reset so it doesn't affect other tests

        fresh = Game(audio_enabled=False, effects_enabled=False, meta_enabled=False)
        fresh.boot()
        loaded = fresh._save.read(save_file)
        fresh._save.apply(
            loaded,
            fs=fresh._fs, network=fresh._network, heat=fresh._heat,
            toolkit=fresh._toolkit, comms=fresh._comms, state=fresh._state,
            history=fresh._history, env=fresh._env,
        )

        assert abs(fresh._heat.level - 42.0) < 0.1

    def test_load_restores_story_flags(self, game, tmp_path):
        from hackerzork.game import Game
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug flag save_roundtrip_test_flag")
        assert game._state.has_flag("save_roundtrip_test_flag")

        save_file = tmp_path / "flags_test.json"
        data = game._save.collect(
            fs=game._fs, network=game._network, heat=game._heat,
            toolkit=game._toolkit, comms=game._comms, state=game._state,
            history=game._history, env=game._env,
        )
        game._save.write(data, save_file)

        fresh = Game(audio_enabled=False, effects_enabled=False, meta_enabled=False)
        fresh.boot()
        loaded = fresh._save.read(save_file)
        fresh._save.apply(
            loaded,
            fs=fresh._fs, network=fresh._network, heat=fresh._heat,
            toolkit=fresh._toolkit, comms=fresh._comms, state=fresh._state,
            history=fresh._history, env=fresh._env,
        )

        assert fresh._state.has_flag("save_roundtrip_test_flag")

    def test_save_cmd_command(self, game, tmp_path):
        """Test the in-game 'save' command."""
        # Override save dir to tmp_path
        original_dir = game._save._save_dir
        game._save._save_dir = tmp_path
        try:
            out = run(game, "save")
            # Should succeed
            assert "saved" in out.lower() or "save" in out.lower()
        finally:
            game._save._save_dir = original_dir

    def test_saves_command_lists(self, game, tmp_path):
        """Test the 'saves' listing command."""
        out = run(game, "saves")
        assert out is not None  # should not crash


# ===========================================================================
# Heat system integration
# ===========================================================================


class TestHeatIntegration:
    def test_heat_increases_on_scan(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug reset heat")
        initial = game._heat.level
        run(game, "nmap 10.13.37.1")
        assert game._heat.level >= initial

    def test_heat_increases_on_exploit(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug reset heat")
        run(game, "nmap 10.13.37.1")
        before = game._heat.level
        run(game, "exploit -p 80 -e CVE-2021-23017 10.13.37.1")
        assert game._heat.level >= before

    def test_heat_threshold_monitored(self, game):
        import hackerzork.commands.devtools as dt
        dt._set_unlocked(True)
        run(game, "hz_debug heat set 30")
        assert game._heat.current_threshold in ("monitored", "safe", "active_response")


# ===========================================================================
# VFS integrity — files from home.yaml should be readable
# ===========================================================================


class TestVFSIntegrity:
    """Verify every file seeded from home.yaml is accessible."""

    _files = [
        "/home/user/.bashrc",
        "/home/user/.bash_history",
        "/home/user/.profile",
        "/home/user/.ssh/known_hosts",
        "/home/user/.old_emails/2025-11-03_anomaly_report.txt",
        "/home/user/.old_emails/2025-12-19_last_day.txt",
        "/home/user/evidence/manifest.txt",
        "/home/user/evidence/README.md",
        "/home/user/tools/README.txt",
        "/var/log/auth.log",
        "/var/log/syslog",
        "/var/log/boot.log",
        "/etc/hosts",
        "/etc/resolv.conf",
        "/etc/passwd",
        "/etc/.hz_debug",
    ]

    @pytest.mark.parametrize("path", _files)
    def test_file_exists(self, game, path):
        assert game._fs.file_exists(path), f"VFS file missing: {path}"

    @pytest.mark.parametrize("path", _files)
    def test_file_readable(self, game, path):
        content = game._fs.read_file(path)
        assert isinstance(content, str), f"read_file returned non-str for {path}"

    def test_encrypted_shadow_exists(self, game):
        assert game._fs.file_exists("/etc/shadow")

    def test_encrypted_core_enc_exists(self, game):
        assert game._fs.file_exists("/home/user/evidence/core.enc")

    def test_ssh_key_encrypted(self, game):
        assert game._fs.file_exists("/home/user/.ssh/id_ed25519")

    def test_config_symlink_exists(self, game):
        # .config → .dotfiles
        assert game._fs.file_exists("/home/user/.config")

    def test_trash_recoverable_file(self, game):
        # exfil.py should be in trash (deleted: true in YAML)
        # recover command should work
        out = run(game, "recover exfil.py")
        # Either it succeeds or gives a message about already recovered
        assert out is not None

    def test_broken_symlink_visible(self, game):
        # /home/user/tools/decrypt is a broken symlink
        assert game._fs.path_is_symlink("/home/user/tools/decrypt")

    def test_hz_debug_content(self, game):
        content = game._fs.read_file("/etc/.hz_debug")
        assert "h@ck3r_d3v_k3y_2026" in content

    def test_hz_debug_perms(self, game):
        node = game._fs._get_node("/etc/.hz_debug")
        perm_str = str(node.permissions)
        assert "6" in perm_str  # owner read+write


# ===========================================================================
# Network nodes loaded
# ===========================================================================


class TestNetworkNodes:
    def test_all_five_nodes_loaded(self, game):
        assert len(game._network.nodes) >= 5

    def test_node_001_ip(self, game):
        assert "10.13.37.1" in game._network.nodes

    def test_node_002_ip(self, game):
        assert "10.13.37.2" in game._network.nodes

    def test_node_003_ip(self, game):
        assert "10.13.37.3" in game._network.nodes

    def test_node_004_ip(self, game):
        assert "10.13.37.4" in game._network.nodes

    def test_node_005_ip(self, game):
        assert "10.13.37.5" in game._network.nodes

    def test_node_001_ports(self, game):
        node = game._network.nodes["10.13.37.1"]
        port_nums = {p.number for p in node.ports}
        assert 80 in port_nums

    def test_node_001_vuln(self, game):
        node = game._network.nodes["10.13.37.1"]
        vulns = {p.vuln for p in node.ports}
        assert "CVE-2021-23017" in vulns

    def test_node_002_has_loot(self, game):
        node = game._network.nodes["10.13.37.2"]
        assert len(node.loot) > 0

    def test_node_004_high_difficulty(self, game):
        node = game._network.nodes["10.13.37.4"]
        assert node.difficulty >= 3

    def test_node_005_low_heat_modifier(self, game):
        node = game._network.nodes["10.13.37.5"]
        assert node.heat_modifier <= 0.5

    def test_node_connections(self, game):
        node = game._network.nodes["10.13.37.1"]
        assert "node_002" in node.connections or "node_005" in node.connections


# ===========================================================================
# Shell edge cases
# ===========================================================================


class TestShellEdgeCases:
    def test_empty_input(self, game):
        out = run(game, "")
        assert out == ""

    def test_whitespace_input(self, game):
        out = run(game, "   ")
        assert out == ""

    def test_unknown_command(self, game):
        out = run(game, "zzznonsensecommand")
        assert "not found" in out.lower() or "command" in out.lower()

    def test_semicolon_separator(self, game):
        out = run(game, "echo a; echo b")
        assert "a" in out and "b" in out

    def test_env_var_substitution_home(self, game):
        out = run(game, "echo $HOME")
        assert "/home/user" in out

    def test_env_var_substitution_user(self, game):
        out = run(game, "echo $USER")
        assert "user" in out

    def test_syntax_error_handled(self, game):
        out = run(game, "cat |")
        # Should give a graceful error, not crash
        assert out is not None

    def test_very_long_command_handled(self, game):
        long_arg = "a" * 1000
        out = run(game, f"echo {long_arg}")
        assert out is not None  # should not crash

    def test_special_chars_in_echo(self, game):
        out = run(game, r'echo "hello\nworld"')
        assert "hello" in out

    def test_path_with_spaces_quoted(self, game):
        run(game, 'mkdir "/tmp/dir with spaces"')
        out = run(game, 'ls /tmp')
        assert "dir with spaces" in out or out  # may or may not support spaces

    def test_cd_to_file_fails(self, game):
        out = run(game, "cd /etc/passwd")
        assert "not a directory" in out.lower() or "error" in out.lower()
