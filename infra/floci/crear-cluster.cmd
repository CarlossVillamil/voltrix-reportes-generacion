@echo off
rem Crea el cluster voltrix-reportes en Floci EKS
rem Requiere: Floci arriba, AWS CLI v2 y kubectl
setlocal EnableExtensions
cd /d "%~dp0"

set "CLUSTER=voltrix-reportes"
set "REGION=us-east-1"
set "ENDPOINT=http://localhost:4566"
set "CUENTA=000000000000"

rem Perfil con credenciales de prueba
echo [1/6] Perfil floci
aws configure set aws_access_key_id test --profile floci
aws configure set aws_secret_access_key test --profile floci
aws configure set region %REGION% --profile floci
aws configure set endpoint_url %ENDPOINT% --profile floci

rem Validar que Floci responda
echo [2/6] Probando Floci en %ENDPOINT%
aws sts get-caller-identity --profile floci >nul 2>&1
if errorlevel 1 (
  echo     Floci no responde. Levantalo con: docker compose up -d
  exit /b 1
)

rem Crear rol del cluster si no existe
echo [3/6] Rol eks-cluster-role
aws iam get-role --role-name eks-cluster-role --profile floci >nul 2>&1
if errorlevel 1 aws iam create-role --role-name eks-cluster-role --assume-role-policy-document file://politica-confianza-eks.json --profile floci >nul

rem Usuario y llave para kubectl (Floci no acepta test/test)
echo [4/6] Usuario equipo4-k8s
aws iam get-user --user-name equipo4-k8s --profile floci >nul 2>&1
if errorlevel 1 aws iam create-user --user-name equipo4-k8s --profile floci >nul
if not exist llave-k8s.txt (
  aws iam create-access-key --user-name equipo4-k8s --query "AccessKey.[AccessKeyId,SecretAccessKey]" --output text --profile floci > llave-k8s.txt
)
rem Cargar la llave en el perfil floci-k8s
for /f "usebackq tokens=1,2" %%a in ("llave-k8s.txt") do (
  aws configure set aws_access_key_id %%a --profile floci-k8s
  aws configure set aws_secret_access_key %%b --profile floci-k8s
)
aws configure set region %REGION% --profile floci-k8s
aws configure set endpoint_url %ENDPOINT% --profile floci-k8s

rem Crear cluster si no existe y esperar a que quede ACTIVE
echo [5/6] Cluster %CLUSTER%
aws eks describe-cluster --name %CLUSTER% --profile floci >nul 2>&1
if errorlevel 1 aws eks create-cluster --name %CLUSTER% --role-arn arn:aws:iam::%CUENTA%:role/eks-cluster-role --resources-vpc-config "{}" --profile floci >nul
aws eks wait cluster-active --name %CLUSTER% --profile floci
aws eks describe-cluster --name %CLUSTER% --query "cluster.[name,status,endpoint]" --output table --profile floci

rem Configurar kubectl y probar
echo [6/6] kubeconfig
aws eks update-kubeconfig --name %CLUSTER% --alias floci-%CLUSTER% --profile floci-k8s
kubectl get nodes -o wide

endlocal
