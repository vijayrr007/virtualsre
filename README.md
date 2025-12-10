# VirtualSRE - EKS Cluster MCP Server

A Model Context Protocol (MCP) server that provides read-only access to AWS EKS (Elastic Kubernetes Service) clusters. This server enables querying Kubernetes resources (pods, deployments, services) and Istio service mesh resources (VirtualServices, DestinationRules) through a standardized MCP interface.

## Features

- **Multi-Cluster Support**: Connect to and query multiple EKS clusters
- **Dual Authentication**: Supports both kubeconfig and AWS IAM authentication
- **Comprehensive Resource Access**: Query pods, deployments, services, and Istio resources
- **Multiple Transports**: STDIO (local), SSE (Server-Sent Events), and HTTP streaming
- **Read-Only Operations**: Safe cluster inspection without modification risks
- **Full Metadata**: Returns complete Kubernetes object metadata for detailed analysis
- **Clear System Prompts**: All tools have comprehensive docstrings optimized for LLM consumption

## Architecture

The project consists of three main components:

1. **MCP Server** (`mcp_server.py`): FastMCP-based server exposing Kubernetes/Istio tools
2. **MCP Client** (`mcp_client.py`): Multi-transport client for connecting to the server
3. **Configuration** (`config.py`): Handles kubeconfig and AWS authentication

## Installation

### Prerequisites

- Python 3.13 or higher
- Access to at least one EKS cluster
- Valid kubeconfig file or AWS credentials
- (Optional) Istio installed in cluster for service mesh features

### Install Dependencies

Using `uv` (recommended):

```bash
uv sync
```

Using `pip`:

```bash
pip install -r requirements.txt
# or
pip install fastmcp kubernetes boto3 pyyaml httpx sse-starlette
```

## Configuration

### Kubeconfig Setup

The server uses your kubeconfig file to connect to clusters. By default, it looks for `~/.kube/config`.

```bash
# View available contexts
kubectl config get-contexts

# Set default context
kubectl config use-context my-cluster
```

### Local Kubernetes Clusters

✅ **This MCP server works perfectly with local Kubernetes clusters!**

Supported local setups:
- **Docker Desktop** (with Kubernetes enabled)
- **Minikube**
- **Kind** (Kubernetes in Docker)
- **K3s/K3d**
- **Rancher Desktop**
- **MicroK8s**
- **Orbstack** (with Kubernetes)

#### Quick Setup for Local Development

**Docker Desktop:**
```bash
# Enable Kubernetes in Docker Desktop preferences
# Then verify:
kubectl config current-context
# Should show: docker-desktop

# Run the MCP server:
python main.py --context docker-desktop
```

**Minikube:**
```bash
# Start minikube
minikube start

# Run the MCP server:
python main.py --context minikube
```

**Kind:**
```bash
# Create a local cluster
kind create cluster --name local-dev

# Run the MCP server:
python main.py --context kind-local-dev
```

#### Verify Your Local Cluster

Run the verification script to check compatibility:

```bash
python verify_local_cluster.py
```

This will:
- ✅ Check if kubeconfig is accessible
- ✅ Test cluster connectivity
- ✅ Verify available resources
- ✅ Test the MCP client
- ✅ Check if Istio is installed (optional)

### AWS Authentication

For EKS clusters using IAM authentication:

1. Install and configure AWS CLI:
```bash
aws configure
```

2. Update your kubeconfig for EKS:
```bash
aws eks update-kubeconfig --region us-east-1 --name my-cluster
```

3. Set AWS environment variables (optional):
```bash
export AWS_REGION=us-east-1
export AWS_PROFILE=default
```

## Usage

### Starting the MCP Server

#### STDIO Transport (Default)

Best for local development and direct integration:

```bash
python main.py
```

With custom kubeconfig:

```bash
python main.py --kubeconfig /path/to/kubeconfig
```

With specific default context:

```bash
python main.py --context prod-cluster
```

#### SSE Transport (Server-Sent Events)

For HTTP-based streaming communication:

```bash
python main.py --transport sse --host 0.0.0.0 --port 8000
```

#### HTTP Transport

For standard HTTP request/response:

```bash
python main.py --transport http --host 0.0.0.0 --port 8000
```

#### List Available Contexts

```bash
python main.py --list-contexts
```

### Using the MCP Client

#### STDIO Transport Example

```python
import asyncio
from mcp_client import create_client

async def main():
    # Create client with STDIO transport
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # List all pods
        pods = await client.list_all_pods()
        print(f"Total pods: {len(pods)}")
        
        # List pods in specific namespace
        pods = await client.list_pods_in_namespace("default")
        
        # List deployments
        deployments = await client.list_deployments_in_namespace("production")
        
        # List services
        services = await client.list_services_in_namespace("default")
        
        # List Istio VirtualServices
        vs = await client.list_istio_virtual_services("default")
        
        # List Istio DestinationRules
        dr = await client.list_istio_destination_rules("default")

asyncio.run(main())
```

#### SSE Transport Example

```python
from mcp_client import create_client

async def main():
    client = create_client(
        transport="sse",
        base_url="http://localhost:8000",
        api_key="your-api-key"  # Optional
    )
    
    async with client:
        pods = await client.list_pods_in_namespace("default")
        print(pods)
```

#### HTTP Transport Example

```python
from mcp_client import create_client

async def main():
    client = create_client(
        transport="http",
        base_url="http://localhost:8000"
    )
    
    async with client:
        services = await client.list_services_in_namespace("kube-system")
        print(services)
```

#### Multi-Cluster Operations

```python
from mcp_client import create_client

async def main():
    client = create_client(transport="stdio", server_script_path="./mcp_server.py")
    
    async with client:
        # Get available contexts
        contexts = await client.list_available_contexts()
        print(f"Available clusters: {contexts}")
        
        # Query specific cluster
        pods = await client.list_all_pods(cluster_context="prod-cluster")
        
        # Query another cluster
        pods = await client.list_all_pods(cluster_context="staging-cluster")
```

### Running Examples

A comprehensive example script is provided:

```bash
python example_usage.py
```

This demonstrates:
- All transport types
- Multi-cluster operations
- Error handling
- Istio service mesh queries
- All available tools

## Available Tools

The MCP server provides **22 comprehensive tools** for querying Kubernetes and Istio resources.

### Cluster & Namespace Tools

#### 1. `list_available_contexts()`
Lists all cluster contexts from kubeconfig.
- **Returns**: List of context names

#### 2. `list_namespaces(cluster_context: Optional[str] = None)`
Lists all namespaces in the cluster.
- **Parameters**: `cluster_context` (optional)
- **Returns**: List of namespace objects with full metadata

#### 3. `list_nodes(cluster_context: Optional[str] = None)`
Lists all nodes in the cluster.
- **Parameters**: `cluster_context` (optional)
- **Returns**: List of node objects with capacity, conditions, and resource information

### Workload Tools

#### 4. `list_all_pods(cluster_context: Optional[str] = None)`
Lists all pods across all namespaces in the cluster.
- **Parameters**: `cluster_context` (optional)
- **Returns**: List of pod objects with full metadata

#### 5. `list_pods_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all pods in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of pod objects with full metadata

#### 6. `list_deployments_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all deployments in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of deployment objects with full metadata

#### 7. `list_statefulsets_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all StatefulSets in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of StatefulSet objects with full metadata

#### 8. `list_daemonsets_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all DaemonSets in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of DaemonSet objects with full metadata

#### 9. `list_jobs_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all Jobs in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of Job objects with full metadata

#### 10. `list_cronjobs_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all CronJobs in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of CronJob objects with schedule and status

### Network & Service Tools

#### 11. `list_services_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all services in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of service objects with full metadata

#### 12. `list_ingresses_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all Ingresses in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of Ingress objects with routing rules and TLS config

### Configuration Tools

#### 13. `list_configmaps_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all ConfigMaps in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of ConfigMap objects with configuration data

#### 14. `list_secrets_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all Secrets (metadata only) in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of Secret objects (data values hidden for security)
- **Security**: Only returns metadata, not actual secret values

### Monitoring & Debugging Tools

#### 15. `list_events_in_namespace(namespace: str, cluster_context: Optional[str] = None)`
Lists all Events in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of Event objects with reasons and messages

#### 16. `get_pod_logs(pod_name: str, namespace: str, container: Optional[str] = None, tail_lines: int = 100, cluster_context: Optional[str] = None)`
Gets logs from a specific pod.
- **Parameters**: `pod_name` (required), `namespace` (required), `container` (optional), `tail_lines` (default: 100), `cluster_context` (optional)
- **Returns**: Dictionary with pod logs

### Istio Service Mesh Tools

#### 17. `list_istio_virtual_services(namespace: str, cluster_context: Optional[str] = None)`
Lists all Istio VirtualServices in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of VirtualService objects with routing rules
- **Note**: Requires Istio. Supports v1alpha3 and v1beta1.

#### 18. `list_istio_destination_rules(namespace: str, cluster_context: Optional[str] = None)`
Lists all Istio DestinationRules in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of DestinationRule objects with traffic policies
- **Note**: Requires Istio. Supports v1alpha3 and v1beta1.

#### 19. `list_istio_gateways(namespace: str, cluster_context: Optional[str] = None)`
Lists all Istio Gateways in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of Gateway objects with ingress/egress configurations
- **Note**: Requires Istio. Supports v1alpha3 and v1beta1.

#### 20. `list_istio_service_entries(namespace: str, cluster_context: Optional[str] = None)`
Lists all Istio ServiceEntries in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of ServiceEntry objects for external service integration
- **Note**: Requires Istio. Supports v1alpha3 and v1beta1.

#### 21. `list_istio_peer_authentications(namespace: str, cluster_context: Optional[str] = None)`
Lists all Istio PeerAuthentication policies in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of PeerAuthentication objects with mTLS settings
- **Note**: Requires Istio. Supports v1beta1 and v1.

#### 22. `list_istio_authorization_policies(namespace: str, cluster_context: Optional[str] = None)`
Lists all Istio AuthorizationPolicy resources in a specific namespace.
- **Parameters**: `namespace` (required), `cluster_context` (optional)
- **Returns**: List of AuthorizationPolicy objects with access control rules
- **Note**: Requires Istio. Supports v1beta1 and v1.

## Return Data Structure

All tools return complete Kubernetes object metadata including:

### Pod Structure
```json
{
  "metadata": {
    "name": "pod-name",
    "namespace": "default",
    "labels": {...},
    "annotations": {...},
    "creation_timestamp": "2024-01-01T00:00:00Z"
  },
  "spec": {
    "containers": [...],
    "volumes": [...],
    "node_name": "node-1"
  },
  "status": {
    "phase": "Running",
    "pod_ip": "10.0.1.5",
    "container_statuses": [...]
  }
}
```

### Deployment Structure
```json
{
  "metadata": {...},
  "spec": {
    "replicas": 3,
    "selector": {...},
    "template": {...},
    "strategy": {...}
  },
  "status": {
    "replicas": 3,
    "ready_replicas": 3,
    "conditions": [...]
  }
}
```

### Service Structure
```json
{
  "metadata": {...},
  "spec": {
    "type": "LoadBalancer",
    "selector": {...},
    "ports": [...]
  },
  "status": {
    "load_balancer": {...}
  }
}
```

## Error Handling

The server returns error objects in the following format:

```json
{
  "error": "Error description",
  "details": "Additional details",
  "namespace": "affected-namespace"
}
```

Common error scenarios:
- **Invalid cluster context**: Context doesn't exist in kubeconfig
- **Authentication failure**: Invalid credentials or expired tokens
- **Namespace not found**: Returns empty list or error
- **Istio not installed**: Returns error message for Istio resources
- **Permission denied**: Insufficient RBAC permissions

## Security Considerations

- **Read-Only**: All operations are read-only by default
- **RBAC**: Respects Kubernetes RBAC policies
- **Credentials**: Uses existing kubeconfig or AWS credentials
- **No Modifications**: Server cannot create, update, or delete resources
- **Safe Inspection**: Suitable for production cluster monitoring

## Troubleshooting

### Connection Issues

```bash
# Verify kubeconfig
kubectl config view

# Test cluster connectivity
kubectl get nodes

# Check AWS credentials
aws sts get-caller-identity

# Verify EKS access
aws eks describe-cluster --name my-cluster --region us-east-1
```

### Permission Errors

Ensure your service account or IAM role has these permissions:
- `pods/list` (in all namespaces or specific namespaces)
- `deployments/list`
- `services/list`
- `virtualservices/list` (for Istio)
- `destinationrules/list` (for Istio)

### Istio Not Found

If you get "CRD not found" errors for Istio resources:

```bash
# Check if Istio is installed
kubectl get crd | grep istio

# Install Istio (if needed)
istioctl install --set profile=demo
```

## Development

### Project Structure

```
virtualsre/
├── main.py              # CLI entry point
├── mcp_server.py        # FastMCP server implementation
├── mcp_client.py        # Multi-transport MCP client
├── config.py            # Configuration management
├── example_usage.py     # Usage examples
├── pyproject.toml       # Dependencies
└── README.md            # Documentation
```

### Adding New Tools

To add a new tool to the server:

1. Define the tool function in `mcp_server.py`:

```python
@mcp.tool()
def my_new_tool(namespace: str, cluster_context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Comprehensive docstring with:
    - PURPOSE: What the tool does
    - WHEN TO USE: Use cases
    - PARAMETERS: Parameter descriptions
    - RETURNS: Return value structure
    - ERROR CONDITIONS: Possible errors
    - EXAMPLE USAGE: Usage examples
    """
    # Implementation
    pass
```

2. Add corresponding method to `EKSMCPClient` in `mcp_client.py`:

```python
async def my_new_tool(self, namespace: str, cluster_context: Optional[str] = None):
    """Call my_new_tool."""
    args = {"namespace": namespace}
    if cluster_context:
        args["cluster_context"] = cluster_context
    return await self.transport.call_tool("my_new_tool", args)
```

### Testing

```bash
# Run example script
python example_usage.py

# Test specific namespace
python -c "import asyncio; from mcp_client import create_client; asyncio.run(create_client('stdio', server_script_path='./mcp_server.py').list_pods_in_namespace('default'))"
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review example usage

## Roadmap

Future enhancements:
- [ ] Support for more Kubernetes resources (ConfigMaps, Secrets, etc.)
- [ ] Write operations (with appropriate safeguards)
- [ ] Real-time streaming of pod logs
- [ ] Metrics and monitoring integration
- [ ] Support for Helm releases
- [ ] Multi-cloud support (GKE, AKS)
- [ ] Web UI for visual cluster exploration

## Acknowledgments

Built with:
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP framework
- [Kubernetes Python Client](https://github.com/kubernetes-client/python) - Kubernetes API access
- [Boto3](https://github.com/boto/boto3) - AWS SDK for Python

