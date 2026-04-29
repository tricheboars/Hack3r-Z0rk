resource "proxmox_virtual_environment_container" "hackerzork" {
  description = "H@ck3r-Z0rk WebSocket game server"
  tags        = ["game", "hackerzork"]

  node_name    = "proxmox2"
  vm_id        = 200
  unprivileged = true
  started      = true

  # ── OS template ────────────────────────────────────────────────────────────
  operating_system {
    template_file_id = "local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst"
    type             = "debian"
  }

  # ── Init: hostname, network, SSH keys ──────────────────────────────────────
  initialization {
    hostname = "hackerzork"

    ip_config {
      ipv4 {
        address = "dhcp"
      }
    }

    user_account {
      keys = [
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIIwuIkSuY4u374KNMo3nc1MguVWcmaGg4+C2BAk2d3VA patrick-proxmox",
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIPJz0MdftlGtlng8R0glVVYC8EaU+COVW3y2qw1lWzu7 patrick@macbook",
      ]
      password = var.lxc_root_password
    }
  }

  # ── Resources ──────────────────────────────────────────────────────────────
  cpu {
    cores = 1
  }

  memory {
    dedicated = 512
    swap      = 512
  }

  # ── Disk — 8 GB on local-zfs ───────────────────────────────────────────────
  disk {
    datastore_id = "local-zfs"
    size         = 8
  }

  # ── Network — VLAN40 DMZ on vmbr0 ─────────────────────────────────────────
  network_interface {
    name    = "eth0"
    bridge  = "vmbr0"
    vlan_id = 40
  }
}

output "hackerzork_ip" {
  description = "LXC IP address (after DHCP — check your router or `pct exec 200 -- ip addr`)"
  value       = "Run: ssh proxmox2 'pct exec 200 -- ip -4 addr show eth0'"
}
