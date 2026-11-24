output "nombre_cluster" {
  value = aws_eks_cluster.this.name
}

output "endpoint_cluster" {
  description = "API server de Kubernetes"
  value       = aws_eks_cluster.this.endpoint
}

output "estado_cluster" {
  value = aws_eks_cluster.this.status
}

output "comando_kubeconfig" {
  description = "Conectar kubectl al cluster"
  value       = "aws eks update-kubeconfig --name ${aws_eks_cluster.this.name} --alias floci-${aws_eks_cluster.this.name} --profile floci-k8s"
}
