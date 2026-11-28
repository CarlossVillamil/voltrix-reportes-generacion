@echo off
rem Construye la imagen de la API y la carga en el nodo k3s de Floci
rem Uso: infra\floci\cargar-imagen.cmd [tag]   (por defecto: avance2)
setlocal EnableExtensions
cd /d "%~dp0..\.."

set "TAG=%~1"
if "%TAG%"=="" set "TAG=avance2"
set "IMAGEN=000000000000.dkr.ecr.us-east-1.localhost:4566/voltrix/reportes-api:%TAG%"
set "NODO=floci-aws-eks-voltrix-reportes"
set "TAR=%TEMP%\reportes-api.tar"

rem Construir la imagen con el Dockerfile del repo
echo [1/4] Construyendo %IMAGEN%
docker build -t %IMAGEN% .
if errorlevel 1 exit /b 1

rem Exportarla a un .tar temporal (fuera del repo)
echo [2/4] Exportando
docker save %IMAGEN% -o "%TAR%"
if errorlevel 1 exit /b 1

rem Copiarla al nodo e importarla en containerd (el ECR de Floci no es alcanzable desde el Docker del host)
echo [3/4] Cargando en el nodo %NODO%
docker cp "%TAR%" %NODO%:/tmp/reportes-api.tar
if errorlevel 1 exit /b 1
docker exec %NODO% ctr -n k8s.io images import /tmp/reportes-api.tar
docker exec %NODO% rm -f /tmp/reportes-api.tar
del "%TAR%"

rem Verificar que el nodo la ve
echo [4/4] Imagen en el nodo
docker exec %NODO% crictl images | findstr reportes-api
endlocal
