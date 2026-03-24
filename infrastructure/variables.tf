variable "proxmox_endpoint" {
  description = "Proxmox API endpoint URL"
  type        = string
  default     = "https://${PROXMOX_NODE1_IP}:8006/"
}

variable "proxmox_api_token" {
  description = "Proxmox API token (set via TF_VAR_proxmox_api_token env var)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "env_suffix" {
  description = "Suffix for environment resources"
  type        = string
  default     = ""
}

variable "vm_id_offset" {
  description = "Offset for VM IDs"
  type        = number
  default     = 0
}
