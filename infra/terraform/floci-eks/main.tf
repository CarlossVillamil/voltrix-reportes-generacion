# Cluster EKS del Equipo 4 sobre Floci

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Todo apunta a Floci, no a AWS
provider "aws" {
  region                      = var.region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = var.floci_endpoint
    eks = var.floci_endpoint
    iam = var.floci_endpoint
    sts = var.floci_endpoint
  }
}

locals {
  etiquetas = {
    Proyecto = "voltrix-energy"
    Equipo   = "equipo-4"
    Servicio = "reportes-generacion"
  }
  zonas = ["${var.region}a", "${var.region}b"]
}

# Red: VPC y dos subredes (EKS pide minimo dos zonas)
resource "aws_vpc" "this" {
  cidr_block           = var.cidr_vpc
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.etiquetas, { Name = "${var.nombre_cluster}-vpc" })
}

resource "aws_subnet" "nodos" {
  count             = length(local.zonas)
  vpc_id            = aws_vpc.this.id
  availability_zone = local.zonas[count.index]
  cidr_block        = cidrsubnet(var.cidr_vpc, 8, count.index)
  tags              = merge(local.etiquetas, { Name = "${var.nombre_cluster}-subred-${count.index}" })
}

# Rol del cluster
resource "aws_iam_role" "cluster" {
  name = "${var.nombre_cluster}-cluster-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.etiquetas
}

# Rol de los nodos
resource "aws_iam_role" "nodos" {
  name = "${var.nombre_cluster}-nodos-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
  tags = local.etiquetas
}

# En AWS real faltan los adjuntos de politicas EKS; Floci no los pide

# Cluster
resource "aws_eks_cluster" "this" {
  name     = var.nombre_cluster
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids = aws_subnet.nodos[*].id
  }

  tags = local.etiquetas
}

# Grupo de nodos (en Floci comparten un solo nodo k3s)
resource "aws_eks_node_group" "general" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "general"
  node_role_arn   = aws_iam_role.nodos.arn
  subnet_ids      = aws_subnet.nodos[*].id
  instance_types  = [var.tipo_instancia_nodo]

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 2
  }

  labels = {
    equipo = "equipo-4"
  }

  tags = local.etiquetas
}
