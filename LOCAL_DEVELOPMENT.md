# Local Development Guide

Complete guide for using VirtualSRE MCP Server with local Kubernetes clusters on your MacBook.

## Prerequisites

1. **Python 3.13+** installed
2. **kubectl** installed (`brew install kubectl`)
3. A local Kubernetes cluster (see options below)

## Choosing Your Local Kubernetes

### Option 1: Docker Desktop (Recommended for Mac)

**Easiest option** - Built into Docker Desktop.

1. Install Docker Desktop: https://www.docker.com/products/docker-desktop
2. Open Docker Desktop preferences
3. Go to "Kubernetes" tab
4. Check "Enable Kubernetes"
5. Click "Apply & Restart"

**Verify:**
```bash
kubectl config current-context
# Should show: docker-desktop

kubectl get nodes
# Should show one node (docker-desktop)
```

### Option 2: Minikube

**Best for isolated testing** - Runs in a VM or container.

```bash
# Install
brew install minikube

# Start cluster
minikube start

# Verify
kubectl config current-context  # Should show: minikube
kubectl get nodes
```

**Useful commands:**
```bash
minikube status        # Check status
minikube stop          # Stop cluster
minikube delete        # Delete cluster
minikube dashboard     # Open Kubernetes dashboard
```

### Option 3: Kind (Kubernetes in Docker)

**Best for CI/CD testing** - Very fast startup.

```bash
# Install
brew install kind

# Create cluster
kind create cluster --name local-dev

# Verify
kubectl config current-context  # Should show: kind-local-dev
kubectl get nodes
```

**Useful commands:**
```bash
kind get clusters                      # List clusters
kind delete cluster --name local-dev   # Delete cluster
```

### Option 4: Orbstack (Modern Docker Desktop Alternative)

```bash
# Install Orbstack
brew install orbstack

# Enable Kubernetes in Orbstack settings
# Context will be: orbstack
```

## Quick Start

### 1. Verify Your Setup

Run the verification script:

```bash
cd /Users/vijaymantena/virtualsre
python verify_local_cluster.py
```

This will check:
- ✅ Kubeconfig accessibility
- ✅ Cluster connectivity
- ✅ Available resources
- ✅ MCP server compatibility

### 2. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 3. Start the MCP Server

```bash
# Start with default context
python main.py

# Or specify your context explicitly
python main.py --context docker-desktop
# or
python main.py --context minikube
# or
python main.py --context kind-local-dev
```

### 4. Test with Examples

```bash
# Run example queries
python example_usage.py
```

## Sample Local Development Workflow

### 1. Deploy Sample Application

```bash
# Create a test namespace
kubectl create namespace test-app

# Deploy nginx
kubectl create deployment nginx --image=nginx --namespace=test-app
kubectl expose deployment nginx --port=80 --namespace=test-app
```

### 2. Query with MCP Client

```python
import asyncio
from mcp_client import create_client

async def test_local():
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # List namespaces
        namespaces = await client.list_namespaces()
        print(f"Namespaces: {[ns['metadata']['name'] for ns in namespaces]}")
        
        # List pods in test-app namespace
        pods = await client.list_pods_in_namespace("test-app")
        for pod in pods:
            name = pod['metadata']['name']
            status = pod['status']['phase']
            print(f"Pod: {name} - {status}")
        
        # List deployments
        deployments = await client.list_deployments_in_namespace("test-app")
        for dep in deployments:
            name = dep['metadata']['name']
            replicas = dep['status'].get('ready_replicas', 0)
            print(f"Deployment: {name} - {replicas} replicas ready")

asyncio.run(test_local())
```

### 3. View Logs

```python
# Get pod logs
logs = await client.get_pod_logs(
    pod_name="nginx-xxx",
    namespace="test-app",
    tail_lines=50
)
print(logs['logs'])
```

## Common Local Development Tasks

### Monitoring Your Local Cluster

```python
async def monitor_cluster():
    """Monitor local cluster health."""
    client = create_client(transport="stdio", server_script_path="./mcp_server.py")
    
    async with client:
        # Check nodes
        nodes = await client.list_nodes()
        for node in nodes:
            name = node['metadata']['name']
            conditions = node['status']['conditions']
            ready = any(c['type'] == 'Ready' and c['status'] == 'True' 
                       for c in conditions)
            print(f"Node {name}: {'Ready' if ready else 'Not Ready'}")
        
        # Check system pods
        system_pods = await client.list_pods_in_namespace("kube-system")
        running = sum(1 for p in system_pods 
                     if p['status']['phase'] == 'Running')
        print(f"System pods: {running}/{len(system_pods)} running")
```

### Testing Istio Locally

If you want to test Istio features:

```bash
# Install Istio on your local cluster
brew install istioctl

# Install Istio
istioctl install --set profile=demo -y

# Verify installation
kubectl get pods -n istio-system

# Now you can test Istio tools
python -c "
import asyncio
from mcp_client import create_client

async def test_istio():
    client = create_client(transport='stdio', server_script_path='./mcp_server.py')
    async with client:
        vs = await client.list_istio_virtual_services('default')
        print(f'VirtualServices: {len(vs)}')

asyncio.run(test_istio())
"
```

## Troubleshooting

### Issue: "Connection refused" or "Unable to connect"

**Solution:**
```bash
# Check if cluster is running
kubectl cluster-info

# For Docker Desktop: Make sure Kubernetes is enabled
# For Minikube: Run 'minikube start'
# For Kind: Verify cluster exists with 'kind get clusters'
```

### Issue: "No kubeconfig found"

**Solution:**
```bash
# Check kubeconfig location
ls -la ~/.kube/config

# If missing, create with kubectl
kubectl config view
```

### Issue: "Context not found"

**Solution:**
```bash
# List available contexts
kubectl config get-contexts

# Use correct context name
python main.py --context <correct-context-name>
```

### Issue: "Permission denied" errors

**Solution:**
Local clusters typically use admin credentials by default, but if you encounter permission issues:

```bash
# For Minikube
minikube kubectl -- auth can-i get pods --all-namespaces

# For Docker Desktop - you have full admin access by default
```

### Issue: MCP server starts but queries fail

**Solution:**
```bash
# Verify cluster is responding
kubectl get pods --all-namespaces

# Run verification script
python verify_local_cluster.py
```

## Resource Limits on Local Clusters

### Docker Desktop

Default resources:
- **CPUs**: 4 cores
- **Memory**: 8 GB
- **Disk**: 60 GB

Adjust in Docker Desktop → Preferences → Resources

### Minikube

```bash
# Start with custom resources
minikube start --cpus=4 --memory=8192 --disk-size=40g

# Check current resources
minikube config view
```

### Kind

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
```

```bash
kind create cluster --config kind-config.yaml
```

## Performance Tips

### 1. Limit Query Scope

```python
# Instead of cluster-wide queries
pods = await client.list_all_pods()  # Slower

# Use namespace-specific queries
pods = await client.list_pods_in_namespace("default")  # Faster
```

### 2. Use Tail Lines for Logs

```python
# Don't fetch entire log
logs = await client.get_pod_logs("pod-name", "default", tail_lines=100)
```

### 3. Cache Context Lists

```python
# Cache this result
contexts = await client.list_available_contexts()
```

## Development with Multiple Local Clusters

You can run multiple local clusters simultaneously:

```bash
# Docker Desktop (always running)
kubectl config use-context docker-desktop

# Start Minikube with different profile
minikube start -p dev-cluster

# Create Kind cluster
kind create cluster --name testing

# List all contexts
kubectl config get-contexts

# Query different clusters with MCP
python -c "
import asyncio
from mcp_client import create_client

async def multi_cluster():
    client = create_client(transport='stdio', server_script_path='./mcp_server.py')
    async with client:
        for ctx in ['docker-desktop', 'minikube', 'kind-testing']:
            try:
                pods = await client.list_all_pods(cluster_context=ctx)
                print(f'{ctx}: {len(pods)} pods')
            except:
                print(f'{ctx}: not available')

asyncio.run(multi_cluster())
"
```

## Next Steps

1. ✅ Verify your setup: `python verify_local_cluster.py`
2. ✅ Start the server: `python main.py`
3. ✅ Run examples: `python example_usage.py`
4. ✅ Read the full documentation: `README.md`
5. ✅ Check tool reference: `TOOLS_REFERENCE.md`

## Useful Resources

- **kubectl Cheat Sheet**: https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- **Docker Desktop Kubernetes**: https://docs.docker.com/desktop/kubernetes/
- **Minikube Docs**: https://minikube.sigs.k8s.io/docs/
- **Kind Quick Start**: https://kind.sigs.k8s.io/docs/user/quick-start/
- **Istio Getting Started**: https://istio.io/latest/docs/setup/getting-started/

Happy local Kubernetes development! 🚀


