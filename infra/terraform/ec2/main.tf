# Instancia EC2 de la API de reportes (AWS real)
# Ojo: apply crea una instancia nueva, no toca la actual (18.222.190.108)

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Credenciales desde el perfil de AWS CLI, nunca en el codigo
provider "aws" {
  region = var.region
}

locals {
  etiquetas = {
    Proyecto = "voltrix-energy"
    Equipo   = "equipo-4"
    Servicio = "reportes-generacion"
  }
}

# Ubuntu 26.04 oficial de Canonical (la misma de la EC2 actual)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-resolute-26.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Solo 22 (IPs del equipo) y 8080
resource "aws_security_group" "reportes" {
  name        = "voltrix-reportes-sg"
  description = "Equipo 4: SSH del equipo y API en 8080"

  ingress {
    description = "SSH del equipo"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.cidrs_ssh
  }

  ingress {
    description = "API de reportes"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Salida libre"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.etiquetas
}

resource "aws_instance" "reportes" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.tipo_instancia
  key_name               = var.nombre_llave
  vpc_security_group_ids = [aws_security_group.reportes.id]

  # Swap, Docker y repo en el primer arranque
  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    swap_mb  = var.swap_mb
    repo_url = var.repo_url
  })

  root_block_device {
    volume_size = var.disco_gb
    volume_type = "gp3"
  }

  # IMDSv2 obligatorio
  metadata_options {
    http_tokens = "required"
  }

  tags = merge(local.etiquetas, { Name = "voltrix-reportes-ec2" })
}

# IP fija opcional (sin ella la IP cambia al detener la instancia)
resource "aws_eip" "reportes" {
  count    = var.usar_ip_elastica ? 1 : 0
  instance = aws_instance.reportes.id
  domain   = "vpc"
  tags     = local.etiquetas
}
