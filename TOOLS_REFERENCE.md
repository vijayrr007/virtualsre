# MCP Tools Reference

Complete reference of all 22 tools available in the VirtualSRE EKS MCP Server.

## Quick Reference Table

| Tool Name | Category | Namespace Required | Description |
|-----------|----------|-------------------|-------------|
| `list_available_contexts` | Cluster | No | List all cluster contexts |
| `list_namespaces` | Cluster | No | List all namespaces |
| `list_nodes` | Cluster | No | List all nodes |
| `list_all_pods` | Workloads | No | List all pods cluster-wide |
| `list_pods_in_namespace` | Workloads | Yes | List pods in namespace |
| `list_deployments_in_namespace` | Workloads | Yes | List deployments in namespace |
| `list_statefulsets_in_namespace` | Workloads | Yes | List StatefulSets in namespace |
| `list_daemonsets_in_namespace` | Workloads | Yes | List DaemonSets in namespace |
| `list_jobs_in_namespace` | Workloads | Yes | List Jobs in namespace |
| `list_cronjobs_in_namespace` | Workloads | Yes | List CronJobs in namespace |
| `list_services_in_namespace` | Network | Yes | List Services in namespace |
| `list_ingresses_in_namespace` | Network | Yes | List Ingresses in namespace |
| `list_configmaps_in_namespace` | Config | Yes | List ConfigMaps in namespace |
| `list_secrets_in_namespace` | Config | Yes | List Secrets (metadata) in namespace |
| `list_events_in_namespace` | Monitoring | Yes | List Events in namespace |
| `get_pod_logs` | Monitoring | Yes | Get pod logs |
| `list_istio_virtual_services` | Istio | Yes | List VirtualServices in namespace |
| `list_istio_destination_rules` | Istio | Yes | List DestinationRules in namespace |
| `list_istio_gateways` | Istio | Yes | List Gateways in namespace |
| `list_istio_service_entries` | Istio | Yes | List ServiceEntries in namespace |
| `list_istio_peer_authentications` | Istio Security | Yes | List PeerAuthentications in namespace |
| `list_istio_authorization_policies` | Istio Security | Yes | List AuthorizationPolicies in namespace |

## Category Breakdown

### 🌐 Cluster Management (3 tools)
Tools for cluster-level operations and discovery.

```python
# List all available cluster contexts
contexts = await client.list_available_contexts()

# List all namespaces
namespaces = await client.list_namespaces()

# List all nodes with capacity and status
nodes = await client.list_nodes()
```

### 🚀 Workload Management (7 tools)
Tools for managing and querying application workloads.

```python
# Pods
all_pods = await client.list_all_pods()
namespace_pods = await client.list_pods_in_namespace("production")

# Deployments
deployments = await client.list_deployments_in_namespace("production")

# StatefulSets (for stateful apps)
statefulsets = await client.list_statefulsets_in_namespace("databases")

# DaemonSets (node-level services)
daemonsets = await client.list_daemonsets_in_namespace("kube-system")

# Jobs & CronJobs
jobs = await client.list_jobs_in_namespace("batch-jobs")
cronjobs = await client.list_cronjobs_in_namespace("scheduled-tasks")
```

### 🔌 Network & Service Management (2 tools)
Tools for networking, load balancing, and ingress.

```python
# Services
services = await client.list_services_in_namespace("production")

# Ingresses (external routing)
ingresses = await client.list_ingresses_in_namespace("production")
```

### ⚙️ Configuration Management (2 tools)
Tools for application configuration and secrets.

```python
# ConfigMaps
configmaps = await client.list_configmaps_in_namespace("production")

# Secrets (metadata only for security)
secrets = await client.list_secrets_in_namespace("production")
```

### 🔍 Monitoring & Debugging (2 tools)
Tools for troubleshooting and observability.

```python
# Events (cluster activities, warnings, errors)
events = await client.list_events_in_namespace("production")

# Pod logs
logs = await client.get_pod_logs(
    pod_name="my-app-xyz",
    namespace="production",
    container="app",
    tail_lines=100
)
```

### 🕸️ Istio Service Mesh (6 tools)
Tools for Istio service mesh configuration and policies.

```python
# Traffic Management
virtual_services = await client.list_istio_virtual_services("production")
destination_rules = await client.list_istio_destination_rules("production")
gateways = await client.list_istio_gateways("istio-system")
service_entries = await client.list_istio_service_entries("production")

# Security Policies
peer_authentications = await client.list_istio_peer_authentications("production")
authorization_policies = await client.list_istio_authorization_policies("production")
```

## Common Use Cases

### 1. Complete Namespace Audit

```python
async def audit_namespace(namespace: str):
    """Get complete view of a namespace."""
    
    # Workloads
    pods = await client.list_pods_in_namespace(namespace)
    deployments = await client.list_deployments_in_namespace(namespace)
    statefulsets = await client.list_statefulsets_in_namespace(namespace)
    
    # Network
    services = await client.list_services_in_namespace(namespace)
    ingresses = await client.list_ingresses_in_namespace(namespace)
    
    # Configuration
    configmaps = await client.list_configmaps_in_namespace(namespace)
    secrets = await client.list_secrets_in_namespace(namespace)
    
    # Events
    events = await client.list_events_in_namespace(namespace)
    
    return {
        "pods": len(pods),
        "deployments": len(deployments),
        "services": len(services),
        # ... etc
    }
```

### 2. Cluster Health Check

```python
async def cluster_health_check():
    """Check overall cluster health."""
    
    # Node status
    nodes = await client.list_nodes()
    unhealthy_nodes = [n for n in nodes 
                       if n.get('status', {}).get('conditions', [])
                       and not is_node_ready(n)]
    
    # System pods
    system_pods = await client.list_pods_in_namespace("kube-system")
    failing_pods = [p for p in system_pods 
                    if p.get('status', {}).get('phase') != 'Running']
    
    # Recent events
    events = await client.list_events_in_namespace("kube-system")
    warnings = [e for e in events if e.get('type') == 'Warning']
    
    return {
        "unhealthy_nodes": len(unhealthy_nodes),
        "failing_system_pods": len(failing_pods),
        "recent_warnings": len(warnings)
    }
```

### 3. Istio Service Mesh Audit

```python
async def istio_mesh_audit(namespace: str):
    """Complete Istio configuration audit."""
    
    # Traffic management
    vs = await client.list_istio_virtual_services(namespace)
    dr = await client.list_istio_destination_rules(namespace)
    gw = await client.list_istio_gateways(namespace)
    se = await client.list_istio_service_entries(namespace)
    
    # Security policies
    pa = await client.list_istio_peer_authentications(namespace)
    ap = await client.list_istio_authorization_policies(namespace)
    
    return {
        "virtual_services": len(vs),
        "destination_rules": len(dr),
        "gateways": len(gw),
        "service_entries": len(se),
        "peer_authentications": len(pa),
        "authorization_policies": len(ap)
    }
```

### 4. Troubleshooting Failed Pods

```python
async def debug_failed_pod(pod_name: str, namespace: str):
    """Debug a failing pod."""
    
    # Get pod details
    pods = await client.list_pods_in_namespace(namespace)
    pod = next((p for p in pods if p['metadata']['name'] == pod_name), None)
    
    if not pod:
        return {"error": "Pod not found"}
    
    # Get pod logs
    logs = await client.get_pod_logs(
        pod_name=pod_name,
        namespace=namespace,
        tail_lines=200
    )
    
    # Get related events
    events = await client.list_events_in_namespace(namespace)
    pod_events = [e for e in events 
                  if e.get('involvedObject', {}).get('name') == pod_name]
    
    return {
        "pod_status": pod.get('status', {}),
        "logs": logs.get('logs', ''),
        "events": pod_events
    }
```

### 5. Resource Utilization Report

```python
async def resource_report():
    """Generate cluster resource utilization report."""
    
    nodes = await client.list_nodes()
    all_pods = await client.list_all_pods()
    
    total_cpu = sum(
        node.get('status', {}).get('allocatable', {}).get('cpu', 0) 
        for node in nodes
    )
    
    total_memory = sum(
        node.get('status', {}).get('allocatable', {}).get('memory', 0)
        for node in nodes
    )
    
    running_pods = len([p for p in all_pods 
                        if p.get('status', {}).get('phase') == 'Running'])
    
    return {
        "total_nodes": len(nodes),
        "total_cpu": total_cpu,
        "total_memory": total_memory,
        "running_pods": running_pods,
        "pods_per_node": running_pods / len(nodes) if nodes else 0
    }
```

## Multi-Cluster Operations

All tools support the `cluster_context` parameter for multi-cluster operations:

```python
# Production cluster
prod_pods = await client.list_all_pods(cluster_context="prod-cluster")

# Staging cluster
staging_pods = await client.list_all_pods(cluster_context="staging-cluster")

# Compare across clusters
for context in ["prod", "staging", "dev"]:
    pods = await client.list_all_pods(cluster_context=context)
    print(f"{context}: {len(pods)} pods")
```

## Tool Output Format

All tools return standardized output:

### Success Response
```python
[
    {
        "metadata": {
            "name": "resource-name",
            "namespace": "namespace",
            "labels": {...},
            "annotations": {...}
        },
        "spec": {...},
        "status": {...}
    }
]
```

### Error Response
```python
[
    {
        "error": "Error description",
        "details": "Additional details",
        "namespace": "affected-namespace"
    }
]
```

## Security Notes

1. **Secrets**: `list_secrets_in_namespace` returns only metadata, not secret values
2. **Read-Only**: All operations are read-only by default
3. **RBAC**: Respects Kubernetes RBAC permissions
4. **Credentials**: Uses existing kubeconfig or AWS credentials

## Performance Considerations

- **Large Clusters**: Use namespace-specific queries instead of cluster-wide queries
- **Log Retrieval**: Limit `tail_lines` parameter to avoid large transfers
- **Multi-Cluster**: Query clusters in parallel for faster results
- **Caching**: Consider caching context lists and namespace lists

## API Version Support

| Resource Type | Kubernetes API | Istio API |
|--------------|----------------|-----------|
| Pods, Services, Nodes | v1 (core) | N/A |
| Deployments, StatefulSets, DaemonSets | apps/v1 | N/A |
| Jobs, CronJobs | batch/v1 | N/A |
| Ingresses | networking.k8s.io/v1 | N/A |
| VirtualServices, DestinationRules, Gateways, ServiceEntries | N/A | v1alpha3, v1beta1 |
| PeerAuthentication, AuthorizationPolicy | N/A | v1beta1, v1 |


