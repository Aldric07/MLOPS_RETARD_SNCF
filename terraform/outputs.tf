output "public_ip" {
  value = azurerm_public_ip.ip.ip_address
}

output "ssh" {
  value = "ssh ${var.admin_username}@${azurerm_public_ip.ip.ip_address}"
}
