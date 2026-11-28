# k8s/ · Despliegue en Floci EKS (Equipo 4)

| Archivo | Contenido |
| --- | --- |
| `namespace.yaml` | Namespace `voltrix-reportes` |
| `configmap.yaml` | Configuración de la API (`MODO_SIMULADO`, `MAX_WORKERS`, `DB_POOL_SIZE`, URLs de los Equipos 1 y 2) |
| `secret.example.yaml` | Plantilla de credenciales. El real (`secret.yaml`) no se sube |
| `postgres.yaml` | PersistentVolume + PVC de 1 GiB, Deployment de PostgreSQL (1 réplica, 256 MiB) y Service interno |
| `api.yaml` | Deployment de la API (2 réplicas, 448 MiB, probes) y Service |
| `desplegar.cmd` | Aplica todo en orden y carga los datos de ejemplo |

## Desplegar

Requiere el clúster de `infra/floci` creado.

```
copy k8s\secret.example.yaml k8s\secret.yaml      (cambiar la clave en las dos líneas)
infra\floci\cargar-imagen.cmd
k8s\desplegar.cmd
```

## Probar

```
kubectl port-forward -n voltrix-reportes svc/api-reportes 8080:80
curl.exe http://localhost:8080/health
```

## Decisiones

- **Imagen:** el ECR de Floci no es alcanzable desde el Docker de Windows, así que `cargar-imagen.cmd` la importa directo al nodo y el Deployment usa `imagePullPolicy: Never`. En EKS real se subiría a ECR.
- **Volumen:** Floci arranca k3s sin StorageClass, así que el PersistentVolume se define a mano (`hostPath` en el nodo). En EKS real sería un volumen EBS gp3.
- **Probes de la API:** startup y readiness sobre `/health` (si la base cae, el pod sale del balanceo); liveness por TCP, para no reiniciar las réplicas cuando el problema es la base.
- **Conexiones:** `DB_POOL_SIZE=5` × 2 réplicas = 10, por debajo de `max_connections=20`.

## Borrar

```
kubectl delete namespace voltrix-reportes
kubectl delete pv db-reportes-datos-pv
```
