@echo off
rem Guarda la evidencia del Avance 2 en infra\evidencia\avance2 (un .txt por casilla)
rem Requiere: el servicio desplegado con k8s\desplegar.cmd
setlocal EnableExtensions
cd /d "%~dp0"
set "OUT=evidencia\avance2"
set "NS=voltrix-reportes"
set "NODO=floci-aws-eks-voltrix-reportes"
if not exist "%OUT%" mkdir "%OUT%"
kubectl config use-context floci-voltrix-reportes >nul

echo [1/5] Replicas, pods y Services
(
  echo Fecha: %date% %time%
  echo.
  echo ^> kubectl get deployments,pods,services -n %NS% -o wide
  kubectl get deployments,pods,services -n %NS% -o wide
  echo.
  echo ^> kubectl get endpoints api-reportes -n %NS%
  kubectl get endpoints api-reportes -n %NS%
) > "%OUT%\01-replicas-pods-services.txt" 2>&1

echo [2/5] Volumen, ConfigMap y Secret
(
  echo Fecha: %date% %time%
  echo.
  echo ^> kubectl get pv,pvc -n %NS%
  kubectl get pv,pvc -n %NS%
  echo.
  echo ^> kubectl get configmaps,secrets -n %NS%
  kubectl get configmaps,secrets -n %NS%
  echo.
  echo ^> kubectl get configmap api-reportes-config -n %NS% -o yaml
  kubectl get configmap api-reportes-config -n %NS% -o yaml
) > "%OUT%\02-volumen-configmap-secret.txt" 2>&1

rem describe no muestra los valores del Secret
echo [3/5] Probes y recursos
(
  echo Fecha: %date% %time%
  echo.
  echo ^> kubectl describe deployment api-reportes -n %NS%
  kubectl describe deployment api-reportes -n %NS%
  echo.
  echo ^> kubectl describe deployment db-reportes -n %NS%
  kubectl describe deployment db-reportes -n %NS%
) > "%OUT%\03-probes-recursos.txt" 2>&1

rem Llamadas hechas desde dentro del cluster, por el Service
echo [4/5] La API responde por el Service
(
  echo Fecha: %date% %time%
  echo.
  echo ^> GET http://api-reportes/health
  kubectl exec -n %NS% deploy/api-reportes -- python -c "import urllib.request as u; print(u.urlopen('http://api-reportes/health').read().decode())"
  echo.
  echo ^> GET http://api-reportes/reportes/generacion?plantaId=PL-001^&limit=2  [X-Equipo-Consumidor: equipo-5]
  kubectl exec -n %NS% deploy/api-reportes -- python -c "import urllib.request as u; r=u.Request('http://api-reportes/reportes/generacion?plantaId=PL-001&limit=2', headers={'X-Equipo-Consumidor': 'equipo-5'}); print(u.urlopen(r).read().decode())"
) > "%OUT%\04-api-responde.txt" 2>&1

echo [5/5] Imagen cargada en el nodo
(
  echo Fecha: %date% %time%
  echo.
  echo ^> docker exec %NODO% crictl images ^| findstr reportes-api
  docker exec %NODO% crictl images | findstr reportes-api
) > "%OUT%\05-imagen-en-nodo.txt" 2>&1

echo.
echo Listo. Evidencia en %~dp0%OUT%
dir /b "%OUT%"
endlocal
