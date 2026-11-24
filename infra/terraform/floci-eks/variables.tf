variable "floci_endpoint" {
  description = "URL de Floci"
  type        = string
  default     = "http://localhost:4566"
}

variable "region" {
  description = "Region emulada"
  type        = string
  default     = "us-east-1"
}

# Nombre distinto al de crear-cluster.cmd para que no choquen
variable "nombre_cluster" {
  description = "Nombre del cluster EKS"
  type        = string
  default     = "voltrix-reportes-iac"
}

variable "cidr_vpc" {
  description = "Rango de la VPC"
  type        = string
  default     = "10.40.0.0/16"
}

variable "tipo_instancia_nodo" {
  description = "Tipo de instancia de los nodos"
  type        = string
  default     = "t3.medium"
}
