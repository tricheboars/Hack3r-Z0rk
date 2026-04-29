variable "proxmox_token_id" {
  description = "Proxmox API token ID (format: user@realm!token-name)"
  type        = string
}

variable "proxmox_token_secret" {
  description = "Proxmox API token secret"
  type        = string
  sensitive   = true
}

variable "lxc_root_password" {
  description = "Root password for the hackerzork LXC (console fallback only — SSH keys are primary)"
  type        = string
  sensitive   = true
}
