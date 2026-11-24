@echo off
rem Guarda la evidencia del Avance 1 en infra\evidencia (un .txt por casilla)
rem Requiere: Floci arriba y el cluster creado con floci\crear-cluster.cmd
setlocal EnableExtensions
cd /d "%~dp0"
set "OUT=evidencia"
if not exist "%OUT%" mkdir "%OUT%"

echo [1/6] Docker en modo root
(
  echo Fecha: %date% %time%
  echo.
  echo ^> docker info --format "{{.OperatingSystem}} | {{.OSType}}"
  docker info --format "{{.OperatingSystem}} | {{.OSType}}"
  echo.
  echo ^> docker info --format "{{.SecurityOptions}}"
  docker info --format "{{.SecurityOptions}}"
) > "%OUT%\01-docker-modo-root.txt" 2>&1

echo [2/6] Floci y contenedor k3s
(
  echo Fecha: %date% %time%
  echo.
  echo ^> docker compose -f floci\docker-compose.yml ps
  docker compose -f floci\docker-compose.yml ps
  echo.
  echo ^> docker ps --filter "ancestor=rancher/k3s:latest"
  docker ps --filter "ancestor=rancher/k3s:latest" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
) > "%OUT%\02-floci-k3s.txt" 2>&1

echo [3/6] Cluster en Floci EKS
(
  echo Fecha: %date% %time%
  echo.
  echo ^> aws eks list-clusters --profile floci
  aws eks list-clusters --profile floci
  echo.
  echo ^> aws eks describe-cluster --name voltrix-reportes --profile floci
  aws eks describe-cluster --name voltrix-reportes --query "cluster.{Nombre:name,Estado:status,Endpoint:endpoint,Version:version,Rol:roleArn}" --output table --profile floci
) > "%OUT%\03-cluster-eks.txt" 2>&1

echo [4/6] kubectl contra el cluster
(
  echo Fecha: %date% %time%
  echo.
  echo ^> kubectl config current-context
  kubectl config current-context
  echo.
  echo ^> kubectl get nodes -o wide
  kubectl get nodes -o wide
  echo.
  echo ^> kubectl get pods -A
  kubectl get pods -A
) > "%OUT%\04-kubectl.txt" 2>&1

rem Floci es local: apply sin confirmacion no toca AWS
echo [5/6] Terraform floci-eks (validate + apply)
(
  echo Fecha: %date% %time%
  echo.
  echo ^> terraform -chdir=terraform\floci-eks validate
  terraform -chdir=terraform\floci-eks validate -no-color
  echo.
  echo ^> terraform -chdir=terraform\floci-eks apply -auto-approve
  terraform -chdir=terraform\floci-eks apply -auto-approve -no-color
  echo.
  echo ^> terraform -chdir=terraform\floci-eks output
  terraform -chdir=terraform\floci-eks output -no-color
) > "%OUT%\05-terraform-floci-eks.txt" 2>&1

rem Solo init y validate: nunca apply contra AWS real
echo [6/6] Terraform ec2 (init + validate)
(
  echo Fecha: %date% %time%
  echo.
  echo ^> terraform -chdir=terraform\ec2 init
  terraform -chdir=terraform\ec2 init -input=false -no-color
  echo.
  echo ^> terraform -chdir=terraform\ec2 validate
  terraform -chdir=terraform\ec2 validate -no-color
) > "%OUT%\06-terraform-ec2.txt" 2>&1

echo.
echo Listo. Evidencia en %~dp0%OUT%
dir /b "%OUT%"
endlocal
