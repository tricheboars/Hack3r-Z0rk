terraform {
  required_version = ">= 1.5.0"

  required_providers {
    proxmox = {
      source  = "bpg/proxmox"
      version = "~> 0.66"
    }
  }
}

provider "proxmox" {
  endpoint  = "https://10.1.30.11:8006/"   # proxmox2 API — direct, avoids cluster proxy issue
  api_token = "${var.proxmox_token_id}=${var.proxmox_token_secret}"
  insecure  = true

  ssh {
    agent       = false
    username    = "root"
    private_key = file("~/.ssh/proxmox")
  }
}
