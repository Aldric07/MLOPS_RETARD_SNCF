variable "subscription_id" {
  description = "ID de ta souscription Azure (commande : az account show --query id -o tsv)"
  type        = string
}

variable "repo_url" {
  description = "URL HTTPS de ton repo GitHub"
  type        = string
}

variable "prefix" {
  type    = string
  default = "sncf-mlops"
}

variable "location" {
  type    = string
  default = "francecentral"
}

variable "vm_size" {
  type    = string
  default = "Standard_B2s"
}

variable "admin_username" {
  type    = string
  default = "azureuser"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}
