@echo off
rem Borra el cluster de Floci (no toca la EC2 ni la base de datos)
setlocal
cd /d "%~dp0"
set "CLUSTER=voltrix-reportes"

aws eks delete-cluster --name %CLUSTER% --profile floci
aws eks wait cluster-deleted --name %CLUSTER% --profile floci
rem Quitar el contexto de kubectl
kubectl config delete-context floci-%CLUSTER%
echo Cluster %CLUSTER% eliminado.
endlocal
