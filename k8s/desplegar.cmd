@echo off
rem Despliega el servicio de reportes en el cluster de Floci EKS
rem Requiere: k8s\secret.yaml y la imagen cargada (infra\floci\cargar-imagen.cmd)
setlocal EnableExtensions
cd /d "%~dp0.."
set "NS=voltrix-reportes"

if not exist k8s\secret.yaml (
  echo Falta k8s\secret.yaml. Copia k8s\secret.example.yaml y cambia la clave.
  exit /b 1
)

rem Trabajar sobre el cluster de Floci
kubectl config use-context floci-voltrix-reportes
if errorlevel 1 exit /b 1

echo [1/6] Namespace, configuracion y credenciales
kubectl apply -f k8s\namespace.yaml
kubectl apply -f k8s\configmap.yaml
kubectl apply -f k8s\secret.yaml

rem Script de tablas desde db\init.sql
echo [2/6] Script de la base
kubectl create configmap db-reportes-init -n %NS% --from-file=init.sql=db\init.sql --dry-run=client -o yaml | kubectl apply -f -

echo [3/6] PostgreSQL
kubectl apply -f k8s\postgres.yaml
kubectl rollout status deployment/db-reportes -n %NS% --timeout=180s
if errorlevel 1 exit /b 1

rem Datos de ejemplo (se puede repetir, no duplica filas)
echo [4/6] Datos de ejemplo
kubectl exec -i -n %NS% deploy/db-reportes -- sh -c "psql -q -U $POSTGRES_USER -d reportes" < db\datos_ejemplo.sql

echo [5/6] API con 2 replicas
kubectl apply -f k8s\api.yaml
kubectl rollout status deployment/api-reportes -n %NS% --timeout=180s
if errorlevel 1 exit /b 1

echo [6/6] Estado
kubectl get pods,svc,pvc -n %NS% -o wide
endlocal
