# infra/ · Floci EKS e IaC (Equipo 4)

Responsable: Hector Daniel Carabali Valencia.

| Carpeta | Qué contiene |
| --- | --- |
| `floci/` | `docker-compose.yml` de Floci (AWS local) y los scripts para crear y borrar el clúster con AWS CLI |
| `terraform/floci-eks/` | IaC del clúster EKS sobre Floci: VPC, subredes, roles IAM, clúster y grupo de nodos |
| `terraform/ec2/` | IaC de la instancia EC2 de la API: Security Group (22 y 8080), 1 GiB de swap, Docker y el repositorio clonado |

Los manifiestos de Kubernetes van en `k8s/` (Avance 2).

## Requisitos (Windows)

- Docker Desktop con el motor WSL 2 y contenedores Linux
- AWS CLI v2: `winget install Amazon.AWSCLI`
- kubectl: `winget install Kubernetes.kubectl` (Docker Desktop ya trae uno)
- Terraform: `winget install Hashicorp.Terraform`

## 1. Comprobar que Docker está en modo root

Floci crea el nodo k3s como contenedor privilegiado; con Docker *rootless* o Podman falla.

```
docker info --format "{{.SecurityOptions}}"
docker info --format "{{.OperatingSystem}} | {{.OSType}}"
```

Si la primera salida **no** contiene `name=rootless`, Docker está en modo root. Docker Desktop en Windows siempre corre así.

## 2. Levantar Floci

```
cd infra\floci
docker compose up -d
docker compose logs --tail 20 floci
```

Floci queda en http://localhost:4566 y su consola en http://localhost:4500.

## 3. Crear el clúster (AWS CLI)

```
cd infra\floci
crear-cluster.cmd
```

El script crea los perfiles `floci` y `floci-k8s` de AWS CLI, el rol `eks-cluster-role`, el usuario `equipo4-k8s` (Floci no deja usar `test/test` con kubectl) y el clúster `voltrix-reportes`. Al final ejecuta `kubectl get nodes`, que debe mostrar un nodo `Ready`.

Comprobaciones:

```
aws eks list-clusters --profile floci
aws eks describe-cluster --name voltrix-reportes --profile floci --query cluster.status
kubectl config current-context
kubectl get nodes -o wide
kubectl get pods -A
docker ps --filter "ancestor=rancher/k3s"
```

Para borrarlo y probar desde cero: `eliminar-cluster.cmd`.

## 4. IaC con Terraform

### Clúster en Floci

```
cd infra\terraform\floci-eks
terraform init
terraform plan
terraform apply
```

Crea el clúster `voltrix-reportes-iac` (nombre distinto al del script para que no choquen). Luego se conecta con el comando de la salida `comando_kubeconfig`.

### Instancia EC2 (AWS real)

```
cd infra\terraform\ec2
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
```

`terraform plan` y `apply` necesitan credenciales de la cuenta de AWS del equipo. **No ejecutar `apply` sin hablarlo con Sebastián**: crea una instancia nueva, no modifica la que está en 18.222.190.108.

## Evidencia para el informe

Capturas o salida de:

1. `docker info --format "{{.SecurityOptions}}"` (modo root)
2. `docker compose ps` en `infra\floci`
3. `aws eks describe-cluster --name voltrix-reportes --profile floci --output table`
4. `kubectl get nodes -o wide` y `kubectl get pods -A`
5. `terraform validate` en las dos carpetas de `terraform/`

## Problemas conocidos

| Síntoma | Causa y solución |
| --- | --- |
| `crear-cluster.cmd` dice que Floci no responde | Floci no está arriba: `docker compose up -d` en `infra\floci` |
| El clúster se queda en `CREATING` o el nodo k3s se reinicia | Docker sin modo root o sin memoria: revisar el paso 1 y darle más memoria a Docker Desktop (Settings → Resources) |
| kubectl responde `401 Unauthorized` | Se está usando `test/test`. Usar el contexto creado con `--profile floci-k8s` |
| `endpoint_url` no se reconoce | AWS CLI viejo: actualizar a la versión 2 más reciente |
