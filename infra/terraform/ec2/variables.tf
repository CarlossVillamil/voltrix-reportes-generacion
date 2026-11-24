# 18.222.x.x esta en us-east-2 (Ohio)
variable "region" {
  description = "Region de AWS"
  type        = string
  default     = "us-east-2"
}

# Confirmar con Sebastian
variable "tipo_instancia" {
  description = "Tipo de instancia (1 GiB de RAM)"
  type        = string
  default     = "t3.micro"
}

# Confirmar con Sebastian
variable "nombre_llave" {
  description = "Key pair de AWS"
  type        = string
  default     = "voltrix-reportes-llave"
}

variable "cidrs_ssh" {
  description = "IPs del equipo para SSH (x.x.x.x/32)"
  type        = list(string)
}

variable "swap_mb" {
  description = "Swap en MiB"
  type        = number
  default     = 1024
}

variable "disco_gb" {
  description = "Disco raiz en GiB"
  type        = number
  default     = 16
}

variable "repo_url" {
  description = "Repositorio a clonar"
  type        = string
  default     = "https://github.com/CarlossVillamil/voltrix-reportes-generacion.git"
}

variable "usar_ip_elastica" {
  description = "Asignar IP elastica"
  type        = bool
  default     = false
}
