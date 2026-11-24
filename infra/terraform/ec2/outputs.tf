# IP elastica si existe, si no la publica de la instancia
locals {
  ip_publica = var.usar_ip_elastica ? aws_eip.reportes[0].public_ip : aws_instance.reportes.public_ip
}

output "ip_publica" {
  value = local.ip_publica
}

output "url_health" {
  value = "http://${local.ip_publica}:8080/health"
}

output "comando_ssh" {
  value = "ssh -i %USERPROFILE%\\.ssh\\voltrix-reportes-llave.pem ubuntu@${local.ip_publica}"
}
