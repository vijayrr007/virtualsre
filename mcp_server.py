"""MCP Server for EKS Cluster Operations.

This server provides read-only access to EKS clusters through the Model Context Protocol (MCP).
It supports multiple clusters and provides tools for querying Kubernetes and Istio resources.
"""

from fastmcp import FastMCP
from kubernetes import client
from kubernetes.client.rest import ApiException
from typing import Optional, List, Dict, Any
import json
from config import ClusterConfig


# Initialize FastMCP server
mcp = FastMCP(
    name="eks-cluster-server",
    instructions="""
    This MCP server provides read-only access to AWS EKS (Elastic Kubernetes Service) clusters.
    It allows you to query Kubernetes resources (pods, deployments, services) and Istio service mesh 
    resources (VirtualServices, DestinationRules) across multiple clusters.
    
    All operations are read-only for safety. The server supports both kubeconfig-based authentication
    and AWS IAM-based authentication for EKS clusters.
    
    Use the appropriate tool based on the resource you want to query and specify the cluster context
    if working with multiple clusters.
    """
)

# Global configuration
cluster_config = ClusterConfig()


def serialize_k8s_object(obj: Any) -> Dict[str, Any]:
    """
    Serialize Kubernetes object to dictionary.
    
    Args:
        obj: Kubernetes API object
        
    Returns:
        Dictionary representation of the object
    """
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return obj
    else:
        return {"data": str(obj)}


def get_k8s_clients(context: Optional[str] = None) -> tuple:
    """
    Get Kubernetes API clients for specified context.
    
    Args:
        context: Cluster context name
        
    Returns:
        Tuple of (CoreV1Api, AppsV1Api, CustomObjectsApi)
        
    Raises:
        Exception: If clients cannot be created
    """
    try:
        # Load kubeconfig - this works for local clusters and properly configured EKS
        from kubernetes import config as k8s_config
        k8s_config.load_kube_config(context=context)
        
        # Create API clients using the default configuration
        core_v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()
        custom_api = client.CustomObjectsApi()
        
        return core_v1, apps_v1, custom_api
    except Exception as e:
        raise Exception(f"Failed to create Kubernetes clients: {str(e)}")


@mcp.tool()
def list_all_pods_summary(cluster_context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List ALL pods across ALL namespaces with SUMMARY information (lightweight, efficient).
    
    PURPOSE:
    Returns essential pod information for cluster-wide overview. This is the PREFERRED tool
    for listing pods as it returns only key fields: name, namespace, status, restarts, age.
    Can efficiently handle clusters with 100+ pods.
    
    WHEN TO USE:
    - User asks to "list all pods", "show all pods", "what pods are running" (DEFAULT CHOICE)
    - Getting cluster overview or pod counts
    - Checking pod health status across namespaces
    - Finding pods by name or namespace
    - Any query NOT requiring full pod specifications or detailed debugging
    
    USE list_all_pods (detailed version) ONLY when user explicitly asks for:
    - "detailed", "full", "yaml", "complete" information
    - Container specifications, volumes, environment variables
    - Owner references, labels, annotations
    - Deep debugging of pod configuration
    
    PARAMETERS:
    - cluster_context (optional, str): Cluster context name from kubeconfig
    
    RETURNS:
    List of dictionaries with essential pod info:
    - name: Pod name
    - namespace: Pod namespace  
    - status: Pod phase (Running, Pending, Failed, etc.)
    - restarts: Total container restart count
    - age: Time since pod creation
    - node: Node name where pod is running
    - ready: Containers ready / total containers
    
    EXAMPLE RETURN:
    [
        {
            "name": "nginx-deployment-abc123",
            "namespace": "production",
            "status": "Running",
            "restarts": 0,
            "age": "2d",
            "node": "node-1",
            "ready": "1/1"
        }
    ]
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        pods = core_v1.list_pod_for_all_namespaces(watch=False)
        
        summary_list = []
        for pod in pods.items:
            # Calculate age
            creation_time = pod.metadata.creation_timestamp
            age = ""
            if creation_time:
                from datetime import datetime, timezone
                delta = datetime.now(timezone.utc) - creation_time
                days = delta.days
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                if days > 0:
                    age = f"{days}d"
                elif hours > 0:
                    age = f"{hours}h"
                else:
                    age = f"{minutes}m"
            
            # Calculate restarts
            restarts = 0
            ready_containers = 0
            total_containers = len(pod.spec.containers) if pod.spec.containers else 0
            
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    restarts += cs.restart_count if cs.restart_count else 0
                    if cs.ready:
                        ready_containers += 1
            
            summary_list.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase or "Unknown",
                "restarts": restarts,
                "age": age,
                "node": pod.spec.node_name or "Unscheduled",
                "ready": f"{ready_containers}/{total_containers}"
            })
        
        return summary_list
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body
        }]
    except Exception as e:
        return [{"error": f"Failed to list pods: {str(e)}"}]


@mcp.tool()
def list_all_pods(cluster_context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List ALL pods across ALL namespaces with DETAILED information (use only when needed).
    
    PURPOSE:
    Returns FULL pod specifications including all metadata, specs, and status.
    This tool returns large amounts of data - use list_all_pods_summary for most queries.
    
    WHEN TO USE DETAILED VERSION:
    - User explicitly asks for "detailed", "full", "yaml", "complete" information
    - Deep debugging requiring container specs, volumes, env vars
    - Need labels, annotations, owner references
    - Troubleshooting specific pod configuration issues
    
    FOR NORMAL QUERIES, USE list_all_pods_summary INSTEAD.
    
    DO NOT USE list_pods_in_namespace with "default" - use summary tool for cluster-wide queries!
    
    PARAMETERS:
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context configured in kubeconfig.
      Available contexts can be found in your kubeconfig file.
      
    RETURNS:
    A list of dictionaries, where each dictionary contains complete pod metadata including:
    - metadata: Pod name, namespace, labels, annotations, creation timestamp
    - spec: Pod specification (containers, volumes, service account, etc.)
    - status: Current pod status (phase, conditions, container statuses, IP addresses)
    
    EXAMPLE RETURN STRUCTURE:
    [
        {
            "metadata": {
                "name": "my-app-pod-xyz",
                "namespace": "production",
                "labels": {"app": "my-app"},
                "creation_timestamp": "2024-01-01T00:00:00Z"
            },
            "spec": {
                "containers": [...],
                "node_name": "node-1"
            },
            "status": {
                "phase": "Running",
                "pod_ip": "10.0.1.5",
                "container_statuses": [...]
            }
        }
    ]
    
    ERROR CONDITIONS:
    - Invalid cluster context: Returns error if specified context doesn't exist
    - Authentication failure: Returns error if kubeconfig or AWS credentials are invalid
    - Network issues: Returns error if cluster is unreachable
    - Permission denied: Returns error if service account lacks list permissions
    
    EXAMPLE USAGE:
    - List all pods in default cluster: list_all_pods()
    - List all pods in specific cluster: list_all_pods(cluster_context="prod-cluster")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        pods = core_v1.list_pod_for_all_namespaces(watch=False)
        
        return [serialize_k8s_object(pod) for pod in pods.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body
        }]
    except Exception as e:
        return [{"error": f"Failed to list pods: {str(e)}"}]


@mcp.tool()
def list_pods_in_namespace_summary(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all pods in a specific namespace with SUMMARY information (lightweight, efficient).
    
    PURPOSE:
    Returns essential pod information for a single namespace. This is the PREFERRED tool
    for listing namespace pods as it returns only key fields: name, status, restarts, age.
    
    WHEN TO USE:
    - User asks to "list pods in namespace X" (DEFAULT CHOICE)
    - Checking namespace pod health
    - Finding pods by name within a namespace
    - Any query NOT requiring full pod specifications
    
    USE list_pods_in_namespace (detailed) ONLY for deep debugging or when user asks for
    "detailed", "full", "yaml", or needs container specs/volumes/env vars.
    
    PARAMETERS:
    - namespace (required, str): Kubernetes namespace name
    - cluster_context (optional, str): Cluster context from kubeconfig
    
    RETURNS:
    List of dictionaries with essential pod info (same format as list_all_pods_summary).
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        pods = core_v1.list_namespaced_pod(namespace=namespace, watch=False)
        
        summary_list = []
        for pod in pods.items:
            # Calculate age
            creation_time = pod.metadata.creation_timestamp
            age = ""
            if creation_time:
                from datetime import datetime, timezone
                delta = datetime.now(timezone.utc) - creation_time
                days = delta.days
                hours = delta.seconds // 3600
                minutes = (delta.seconds % 3600) // 60
                if days > 0:
                    age = f"{days}d"
                elif hours > 0:
                    age = f"{hours}h"
                else:
                    age = f"{minutes}m"
            
            # Calculate restarts
            restarts = 0
            ready_containers = 0
            total_containers = len(pod.spec.containers) if pod.spec.containers else 0
            
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    restarts += cs.restart_count if cs.restart_count else 0
                    if cs.ready:
                        ready_containers += 1
            
            summary_list.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase or "Unknown",
                "restarts": restarts,
                "age": age,
                "node": pod.spec.node_name or "Unscheduled",
                "ready": f"{ready_containers}/{total_containers}"
            })
        
        return summary_list
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body
        }]
    except Exception as e:
        return [{"error": f"Failed to list pods in namespace {namespace}: {str(e)}"}]


@mcp.tool()
def list_pods_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all pods in a specific namespace with DETAILED information (use only when needed).
    
    PURPOSE:
    Returns FULL pod specifications. Use list_pods_in_namespace_summary for most queries.
    
    WHEN TO USE DETAILED VERSION:
    - User explicitly asks for "detailed", "full", "yaml" information
    - Deep debugging requiring container specs, volumes, env vars
    
    WHEN TO USE:
    - Investigating issues within a specific application namespace
    - Monitoring pods for a particular service or team
    - Getting namespace-scoped resource information
    - Debugging application deployments in a specific environment
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
      Common namespaces include: default, kube-system, istio-system, or custom app namespaces.
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context from kubeconfig.
      
    RETURNS:
    A list of dictionaries, where each dictionary contains complete pod metadata including:
    - metadata: Pod name, namespace, labels, annotations, owner references
    - spec: Container specifications, volumes, resource requests/limits
    - status: Pod phase, conditions, container statuses, events
    
    EXAMPLE RETURN STRUCTURE:
    [
        {
            "metadata": {
                "name": "nginx-deployment-abc123",
                "namespace": "production",
                "labels": {"app": "nginx", "version": "v1"},
                "owner_references": [{"kind": "ReplicaSet", "name": "nginx-rs"}]
            },
            "spec": {
                "containers": [
                    {
                        "name": "nginx",
                        "image": "nginx:1.21",
                        "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}}
                    }
                ]
            },
            "status": {
                "phase": "Running",
                "conditions": [...],
                "container_statuses": [
                    {
                        "name": "nginx",
                        "ready": true,
                        "restart_count": 0,
                        "state": {"running": {"started_at": "2024-01-01T00:00:00Z"}}
                    }
                ]
            }
        }
    ]
    
    ERROR CONDITIONS:
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - Authentication failure: Returns error if credentials are invalid
    - Permission denied: Returns error if lacking namespace access
    
    EXAMPLE USAGE:
    - List pods in default namespace: list_pods_in_namespace(namespace="default")
    - List pods in production: list_pods_in_namespace(namespace="production", cluster_context="prod-cluster")
    - List system pods: list_pods_in_namespace(namespace="kube-system")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        pods = core_v1.list_namespaced_pod(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(pod) for pod in pods.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list pods in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_deployments_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Deployments in a specific namespace within the specified EKS cluster.
    
    PURPOSE:
    This tool retrieves comprehensive information about Kubernetes Deployments, which manage
    ReplicaSets and provide declarative updates for Pods. Deployments are the primary way
    to manage stateless applications in Kubernetes.
    
    WHEN TO USE:
    - Checking deployment status and health
    - Reviewing deployment configurations and strategies
    - Troubleshooting application rollout issues
    - Auditing deployment replicas and resource allocations
    - Verifying container images and versions in use
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
      Deployments are namespace-scoped resources.
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context from kubeconfig.
      
    RETURNS:
    A list of dictionaries, where each dictionary contains complete deployment metadata including:
    - metadata: Deployment name, namespace, labels, annotations
    - spec: Deployment specification (replicas, selector, template, strategy)
    - status: Current deployment status (available replicas, conditions, observed generation)
    
    EXAMPLE RETURN STRUCTURE:
    [
        {
            "metadata": {
                "name": "nginx-deployment",
                "namespace": "production",
                "labels": {"app": "nginx"},
                "creation_timestamp": "2024-01-01T00:00:00Z"
            },
            "spec": {
                "replicas": 3,
                "selector": {"match_labels": {"app": "nginx"}},
                "template": {
                    "metadata": {"labels": {"app": "nginx"}},
                    "spec": {"containers": [...]}
                },
                "strategy": {
                    "type": "RollingUpdate",
                    "rolling_update": {"max_surge": 1, "max_unavailable": 0}
                }
            },
            "status": {
                "replicas": 3,
                "ready_replicas": 3,
                "available_replicas": 3,
                "updated_replicas": 3,
                "conditions": [
                    {
                        "type": "Available",
                        "status": "True",
                        "reason": "MinimumReplicasAvailable"
                    }
                ]
            }
        }
    ]
    
    ERROR CONDITIONS:
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - Authentication failure: Returns error if credentials are invalid
    - Permission denied: Returns error if lacking deployment read permissions
    
    EXAMPLE USAGE:
    - List deployments: list_deployments_in_namespace(namespace="default")
    - Check production deployments: list_deployments_in_namespace(namespace="production", cluster_context="prod-cluster")
    """
    try:
        _, apps_v1, _ = get_k8s_clients(cluster_context)
        deployments = apps_v1.list_namespaced_deployment(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(deployment) for deployment in deployments.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list deployments in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_services_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Services in a specific namespace within the specified EKS cluster.
    
    PURPOSE:
    This tool retrieves information about Kubernetes Services, which provide stable networking
    endpoints for accessing pods. Services enable load balancing and service discovery within
    the cluster and can expose applications externally.
    
    WHEN TO USE:
    - Investigating networking and connectivity issues
    - Reviewing service endpoints and load balancing configurations
    - Checking exposed ports and service types (ClusterIP, NodePort, LoadBalancer)
    - Troubleshooting service discovery problems
    - Auditing external access points and ingress configurations
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
      Services are namespace-scoped resources.
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context from kubeconfig.
      
    RETURNS:
    A list of dictionaries, where each dictionary contains complete service metadata including:
    - metadata: Service name, namespace, labels, annotations
    - spec: Service specification (type, ports, selector, external IPs)
    - status: Current service status (load balancer ingress, conditions)
    
    EXAMPLE RETURN STRUCTURE:
    [
        {
            "metadata": {
                "name": "nginx-service",
                "namespace": "production",
                "labels": {"app": "nginx"},
                "annotations": {"service.beta.kubernetes.io/aws-load-balancer-type": "nlb"}
            },
            "spec": {
                "type": "LoadBalancer",
                "selector": {"app": "nginx"},
                "ports": [
                    {
                        "name": "http",
                        "protocol": "TCP",
                        "port": 80,
                        "target_port": 8080
                    }
                ],
                "session_affinity": "None"
            },
            "status": {
                "load_balancer": {
                    "ingress": [
                        {"hostname": "abc123.us-east-1.elb.amazonaws.com"}
                    ]
                }
            }
        }
    ]
    
    SERVICE TYPES:
    - ClusterIP: Internal service, only accessible within cluster
    - NodePort: Exposes service on each node's IP at a static port
    - LoadBalancer: Creates an external load balancer (e.g., AWS ELB/NLB)
    - ExternalName: Maps service to external DNS name
    
    ERROR CONDITIONS:
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - Authentication failure: Returns error if credentials are invalid
    - Permission denied: Returns error if lacking service read permissions
    
    EXAMPLE USAGE:
    - List services: list_services_in_namespace(namespace="default")
    - Check production services: list_services_in_namespace(namespace="production", cluster_context="prod-cluster")
    - Review system services: list_services_in_namespace(namespace="kube-system")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        services = core_v1.list_namespaced_service(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(service) for service in services.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list services in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_istio_virtual_services(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Istio VirtualServices in a specific namespace within the specified EKS cluster.
    
    PURPOSE:
    This tool retrieves Istio VirtualService resources, which define traffic routing rules for
    services in the Istio service mesh. VirtualServices allow you to configure advanced routing,
    traffic splitting, retries, timeouts, and fault injection.
    
    WHEN TO USE:
    - Reviewing traffic routing rules and configurations
    - Troubleshooting service mesh routing issues
    - Checking A/B testing or canary deployment configurations
    - Auditing HTTP/gRPC route rules and match conditions
    - Verifying traffic splitting percentages and destination weights
    - Investigating timeout and retry configurations
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
      VirtualServices are namespace-scoped custom resources.
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context from kubeconfig.
      
    RETURNS:
    A list of dictionaries, where each dictionary contains complete VirtualService metadata including:
    - metadata: VirtualService name, namespace, labels, annotations
    - spec: VirtualService specification (hosts, gateways, http/tcp/tls routes)
    - status: Current status (if available)
    
    EXAMPLE RETURN STRUCTURE:
    [
        {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {
                "name": "reviews-route",
                "namespace": "production",
                "labels": {"app": "reviews"}
            },
            "spec": {
                "hosts": ["reviews.production.svc.cluster.local"],
                "http": [
                    {
                        "match": [{"headers": {"user": {"exact": "tester"}}}],
                        "route": [{"destination": {"host": "reviews", "subset": "v2"}}]
                    },
                    {
                        "route": [
                            {"destination": {"host": "reviews", "subset": "v1"}, "weight": 90},
                            {"destination": {"host": "reviews", "subset": "v2"}, "weight": 10}
                        ]
                    }
                ]
            }
        }
    ]
    
    KEY FEATURES EXPOSED:
    - Traffic routing based on HTTP headers, URIs, or methods
    - Weighted traffic distribution for canary deployments
    - Request timeouts and retry policies
    - Fault injection for testing resilience
    - Cross-origin resource sharing (CORS) policies
    - Gateway bindings for ingress traffic
    
    ERROR CONDITIONS:
    - Istio not installed: Returns error if Istio CRDs are not present
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - API version mismatch: May fail if Istio version differs significantly
    - Permission denied: Returns error if lacking CRD read permissions
    
    NOTE:
    This tool checks for VirtualServices in both v1alpha3 and v1beta1 API versions
    to support different Istio versions.
    
    EXAMPLE USAGE:
    - List VirtualServices: list_istio_virtual_services(namespace="default")
    - Check production routes: list_istio_virtual_services(namespace="production", cluster_context="prod-cluster")
    - Review mesh config: list_istio_virtual_services(namespace="istio-system")
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "networking.istio.io"
        plural = "virtualservices"
        
        # Try v1beta1 first (newer Istio versions)
        versions = ["v1beta1", "v1alpha3"]
        
        for version in versions:
            try:
                virtual_services = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return virtual_services.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    # Try next version
                    continue
                else:
                    raise
        
        # If we get here, no version worked
        return [{
            "error": "Istio VirtualService CRD not found",
            "details": "Istio may not be installed or VirtualService CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list VirtualServices in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_istio_destination_rules(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Istio DestinationRules in a specific namespace within the specified EKS cluster.
    
    PURPOSE:
    This tool retrieves Istio DestinationRule resources, which configure policies that apply
    to traffic intended for a service after routing has occurred. DestinationRules define
    load balancing policies, connection pool settings, outlier detection, and TLS settings.
    
    WHEN TO USE:
    - Reviewing load balancing configurations (round-robin, random, least-request)
    - Checking service subset definitions (used by VirtualServices)
    - Troubleshooting connection pool and circuit breaker issues
    - Auditing TLS/mTLS settings for service-to-service communication
    - Investigating outlier detection and health check configurations
    - Verifying traffic policies for specific service versions
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
      DestinationRules are namespace-scoped custom resources.
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context from kubeconfig.
      
    RETURNS:
    A list of dictionaries, where each dictionary contains complete DestinationRule metadata including:
    - metadata: DestinationRule name, namespace, labels, annotations
    - spec: DestinationRule specification (host, subsets, traffic policy)
    - status: Current status (if available)
    
    EXAMPLE RETURN STRUCTURE:
    [
        {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": "reviews-destination",
                "namespace": "production",
                "labels": {"app": "reviews"}
            },
            "spec": {
                "host": "reviews.production.svc.cluster.local",
                "trafficPolicy": {
                    "loadBalancer": {"simple": "LEAST_REQUEST"},
                    "connectionPool": {
                        "tcp": {"maxConnections": 100},
                        "http": {"http1MaxPendingRequests": 50, "maxRequestsPerConnection": 2}
                    },
                    "outlierDetection": {
                        "consecutiveErrors": 5,
                        "interval": "30s",
                        "baseEjectionTime": "30s",
                        "maxEjectionPercent": 50
                    }
                },
                "subsets": [
                    {
                        "name": "v1",
                        "labels": {"version": "v1"},
                        "trafficPolicy": {
                            "loadBalancer": {"simple": "ROUND_ROBIN"}
                        }
                    },
                    {
                        "name": "v2",
                        "labels": {"version": "v2"}
                    }
                ]
            }
        }
    ]
    
    KEY FEATURES EXPOSED:
    - Load balancing algorithms: ROUND_ROBIN, LEAST_REQUEST, RANDOM, PASSTHROUGH
    - Subset definitions based on pod labels (for version-based routing)
    - Connection pool settings: TCP and HTTP connection limits
    - Circuit breaker configuration via outlier detection
    - TLS settings: mutual TLS, client certificates, SNI
    - Port-specific traffic policies
    
    ERROR CONDITIONS:
    - Istio not installed: Returns error if Istio CRDs are not present
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - API version mismatch: May fail if Istio version differs significantly
    - Permission denied: Returns error if lacking CRD read permissions
    
    NOTE:
    This tool checks for DestinationRules in both v1alpha3 and v1beta1 API versions
    to support different Istio versions.
    
    EXAMPLE USAGE:
    - List DestinationRules: list_istio_destination_rules(namespace="default")
    - Check production policies: list_istio_destination_rules(namespace="production", cluster_context="prod-cluster")
    - Review mesh policies: list_istio_destination_rules(namespace="istio-system")
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "networking.istio.io"
        plural = "destinationrules"
        
        # Try v1beta1 first (newer Istio versions)
        versions = ["v1beta1", "v1alpha3"]
        
        for version in versions:
            try:
                destination_rules = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return destination_rules.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    # Try next version
                    continue
                else:
                    raise
        
        # If we get here, no version worked
        return [{
            "error": "Istio DestinationRule CRD not found",
            "details": "Istio may not be installed or DestinationRule CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list DestinationRules in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_available_contexts() -> List[str]:
    """
    List all available Kubernetes cluster contexts from the kubeconfig file.
    
    PURPOSE:
    This tool retrieves the list of cluster contexts configured in your kubeconfig file.
    Contexts represent different Kubernetes clusters or different access configurations
    for the same cluster (e.g., different namespaces or users).
    
    WHEN TO USE:
    - Discovering which clusters are available for querying
    - Verifying cluster connectivity configuration before making requests
    - Debugging connection issues by checking available contexts
    - Choosing the correct context for multi-cluster operations
    
    PARAMETERS:
    None required.
    
    RETURNS:
    A list of context names (strings) available in the kubeconfig file.
    
    EXAMPLE RETURN:
    [
        "minikube",
        "prod-eks-cluster",
        "staging-eks-cluster",
        "dev-cluster"
    ]
    
    ERROR CONDITIONS:
    - Kubeconfig not found: Returns empty list if kubeconfig file doesn't exist
    - Invalid kubeconfig: Returns error if kubeconfig format is invalid
    
    NOTE:
    The contexts returned by this tool can be used as the `cluster_context` parameter
    in other tools to specify which cluster to query.
    
    EXAMPLE USAGE:
    - Get all contexts: list_available_contexts()
    """
    try:
        contexts = cluster_config.get_available_contexts()
        return contexts
    except Exception as e:
        return [f"Error listing contexts: {str(e)}"]


@mcp.tool()
def list_namespaces(cluster_context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all namespaces in the specified EKS cluster.
    
    PURPOSE:
    This tool retrieves all Kubernetes namespaces, which provide logical isolation and
    resource organization within a cluster. Namespaces are fundamental for multi-tenancy
    and separating environments (dev, staging, prod) or teams.
    
    WHEN TO USE:
    - Getting an overview of cluster organization
    - Discovering available namespaces before querying resources
    - Auditing namespace configurations and resource quotas
    - Checking namespace labels and annotations
    
    PARAMETERS:
    - cluster_context (optional, str): The name of the cluster context to query.
      If not provided, uses the default context from kubeconfig.
      
    RETURNS:
    A list of dictionaries containing complete namespace metadata including:
    - metadata: Namespace name, labels, annotations, creation timestamp
    - spec: Namespace specification (finalizers)
    - status: Namespace status (phase)
    
    ERROR CONDITIONS:
    - Invalid cluster context: Returns error if context is invalid
    - Authentication failure: Returns error if credentials are invalid
    - Permission denied: Returns error if lacking namespace list permissions
    
    EXAMPLE USAGE:
    - List all namespaces: list_namespaces()
    - List in specific cluster: list_namespaces(cluster_context="prod-cluster")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        namespaces = core_v1.list_namespace(watch=False)
        
        return [serialize_k8s_object(ns) for ns in namespaces.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body
        }]
    except Exception as e:
        return [{"error": f"Failed to list namespaces: {str(e)}"}]


@mcp.tool()
def list_nodes(cluster_context: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all nodes in the specified EKS cluster.
    
    PURPOSE:
    This tool retrieves information about all worker nodes in the cluster. Nodes are
    the physical or virtual machines that run your workloads. This is crucial for
    capacity planning, troubleshooting, and understanding cluster health.
    
    WHEN TO USE:
    - Checking cluster capacity and node health
    - Investigating node resource utilization
    - Verifying node labels and taints
    - Troubleshooting pod scheduling issues
    - Auditing node configurations and versions
    
    PARAMETERS:
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete node metadata including:
    - metadata: Node name, labels, annotations, taints
    - spec: Node specification (pod CIDR, provider ID, unschedulable flag)
    - status: Node status (conditions, capacity, allocatable resources, node info)
    
    ERROR CONDITIONS:
    - Invalid cluster context: Returns error if context is invalid
    - Authentication failure: Returns error if credentials are invalid
    - Permission denied: Returns error if lacking node list permissions
    
    EXAMPLE USAGE:
    - List all nodes: list_nodes()
    - Check prod nodes: list_nodes(cluster_context="prod-cluster")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        nodes = core_v1.list_node(watch=False)
        
        return [serialize_k8s_object(node) for node in nodes.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body
        }]
    except Exception as e:
        return [{"error": f"Failed to list nodes: {str(e)}"}]


@mcp.tool()
def list_configmaps_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all ConfigMaps in a specific namespace.
    
    PURPOSE:
    This tool retrieves ConfigMap resources, which store non-confidential configuration
    data in key-value pairs. ConfigMaps are used to externalize configuration from
    application code and container images.
    
    WHEN TO USE:
    - Reviewing application configuration
    - Debugging configuration-related issues
    - Auditing configuration data
    - Verifying config updates after deployments
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete ConfigMap metadata including:
    - metadata: ConfigMap name, namespace, labels, annotations
    - data: Configuration key-value pairs
    - binary_data: Binary configuration data (base64 encoded)
    
    ERROR CONDITIONS:
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - Permission denied: Returns error if lacking ConfigMap read permissions
    
    EXAMPLE USAGE:
    - List ConfigMaps: list_configmaps_in_namespace(namespace="default")
    - Check app configs: list_configmaps_in_namespace(namespace="production")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        configmaps = core_v1.list_namespaced_config_map(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(cm) for cm in configmaps.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list ConfigMaps in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_secrets_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Secrets (metadata only) in a specific namespace.
    
    PURPOSE:
    This tool retrieves Secret resource metadata without exposing sensitive data values.
    Secrets store confidential information like passwords, tokens, and keys. For security,
    only metadata is returned (names, labels, type) - not the actual secret values.
    
    WHEN TO USE:
    - Auditing what secrets exist
    - Checking secret types and references
    - Verifying secret creation and updates
    - Investigating missing secret references
    - NOT for retrieving actual secret values (security measure)
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing Secret metadata (WITHOUT secret data) including:
    - metadata: Secret name, namespace, labels, annotations, type
    - type: Secret type (Opaque, kubernetes.io/service-account-token, etc.)
    - Note: 'data' field is excluded for security
    
    ERROR CONDITIONS:
    - Namespace not found: Returns empty list if namespace doesn't exist
    - Invalid cluster context: Returns error if context is invalid
    - Permission denied: Returns error if lacking Secret read permissions
    
    SECURITY NOTE:
    This tool intentionally does NOT return secret values. Only metadata is returned
    to prevent accidental exposure of sensitive information.
    
    EXAMPLE USAGE:
    - List secrets: list_secrets_in_namespace(namespace="default")
    - Check app secrets: list_secrets_in_namespace(namespace="production")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        secrets = core_v1.list_namespaced_secret(namespace=namespace, watch=False)
        
        # Remove sensitive data for security
        result = []
        for secret in secrets.items:
            secret_dict = serialize_k8s_object(secret)
            # Remove actual secret data
            if 'data' in secret_dict:
                secret_dict['data'] = f"<{len(secret_dict['data'])} keys - data hidden for security>"
            if 'string_data' in secret_dict:
                secret_dict['string_data'] = "<data hidden for security>"
            result.append(secret_dict)
        
        return result
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Secrets in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_statefulsets_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all StatefulSets in a specific namespace.
    
    PURPOSE:
    This tool retrieves StatefulSet resources, which manage stateful applications requiring
    stable network identities, persistent storage, and ordered deployment/scaling.
    StatefulSets are used for databases, message queues, and other stateful services.
    
    WHEN TO USE:
    - Checking stateful application deployments
    - Reviewing persistent storage configurations
    - Troubleshooting pod ordering and scaling issues
    - Auditing stateful workload configurations
    - Verifying volume claim templates
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete StatefulSet metadata including:
    - metadata: StatefulSet name, namespace, labels, annotations
    - spec: StatefulSet specification (replicas, selector, template, volume claims)
    - status: Current status (replicas, ready replicas, current revision)
    
    EXAMPLE USAGE:
    - List StatefulSets: list_statefulsets_in_namespace(namespace="default")
    - Check databases: list_statefulsets_in_namespace(namespace="databases")
    """
    try:
        _, apps_v1, _ = get_k8s_clients(cluster_context)
        statefulsets = apps_v1.list_namespaced_stateful_set(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(sts) for sts in statefulsets.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list StatefulSets in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_daemonsets_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all DaemonSets in a specific namespace.
    
    PURPOSE:
    This tool retrieves DaemonSet resources, which ensure that all (or some) nodes run
    a copy of a specific pod. DaemonSets are typically used for node-level services like
    log collectors, monitoring agents, and network plugins.
    
    WHEN TO USE:
    - Checking node-level service deployments
    - Verifying monitoring/logging agent coverage
    - Troubleshooting node daemon issues
    - Auditing cluster-wide service configurations
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete DaemonSet metadata including:
    - metadata: DaemonSet name, namespace, labels, annotations
    - spec: DaemonSet specification (selector, template, update strategy)
    - status: Current status (desired/current/ready number of scheduled pods)
    
    EXAMPLE USAGE:
    - List DaemonSets: list_daemonsets_in_namespace(namespace="kube-system")
    - Check monitoring: list_daemonsets_in_namespace(namespace="monitoring")
    """
    try:
        _, apps_v1, _ = get_k8s_clients(cluster_context)
        daemonsets = apps_v1.list_namespaced_daemon_set(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(ds) for ds in daemonsets.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list DaemonSets in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_jobs_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Jobs in a specific namespace.
    
    PURPOSE:
    This tool retrieves Job resources, which create one or more pods and ensure that
    a specified number successfully terminate. Jobs are used for batch processing,
    one-time tasks, and parallel processing workloads.
    
    WHEN TO USE:
    - Checking batch job execution status
    - Troubleshooting failed jobs
    - Auditing job completion rates
    - Reviewing job configurations and parallelism
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete Job metadata including:
    - metadata: Job name, namespace, labels, annotations
    - spec: Job specification (parallelism, completions, template, backoff limit)
    - status: Current status (active, succeeded, failed, completion time)
    
    EXAMPLE USAGE:
    - List Jobs: list_jobs_in_namespace(namespace="default")
    - Check batch jobs: list_jobs_in_namespace(namespace="batch-processing")
    """
    try:
        _, apps_v1, _ = get_k8s_clients(cluster_context)
        
        # Jobs are in batch/v1 API group
        from kubernetes.client import BatchV1Api
        batch_v1 = BatchV1Api(api_client=apps_v1.api_client)
        
        jobs = batch_v1.list_namespaced_job(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(job) for job in jobs.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Jobs in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_cronjobs_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all CronJobs in a specific namespace.
    
    PURPOSE:
    This tool retrieves CronJob resources, which create Jobs on a repeating schedule
    (like Unix cron). CronJobs are used for periodic tasks like backups, report generation,
    and scheduled maintenance.
    
    WHEN TO USE:
    - Reviewing scheduled job configurations
    - Checking cron schedule expressions
    - Troubleshooting missed or failed scheduled jobs
    - Auditing automated task schedules
    - Verifying job history limits
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete CronJob metadata including:
    - metadata: CronJob name, namespace, labels, annotations
    - spec: CronJob specification (schedule, job template, concurrency policy)
    - status: Current status (last schedule time, active jobs)
    
    EXAMPLE USAGE:
    - List CronJobs: list_cronjobs_in_namespace(namespace="default")
    - Check scheduled tasks: list_cronjobs_in_namespace(namespace="automation")
    """
    try:
        _, apps_v1, _ = get_k8s_clients(cluster_context)
        
        # CronJobs are in batch/v1 API group
        from kubernetes.client import BatchV1Api
        batch_v1 = BatchV1Api(api_client=apps_v1.api_client)
        
        cronjobs = batch_v1.list_namespaced_cron_job(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(cj) for cj in cronjobs.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list CronJobs in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_ingresses_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Ingresses in a specific namespace.
    
    PURPOSE:
    This tool retrieves Ingress resources, which manage external access to services
    in the cluster, typically HTTP/HTTPS. Ingresses provide load balancing, SSL
    termination, and name-based virtual hosting.
    
    WHEN TO USE:
    - Reviewing external routing configurations
    - Checking TLS certificate configurations
    - Troubleshooting ingress routing issues
    - Auditing external access points
    - Verifying host and path rules
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete Ingress metadata including:
    - metadata: Ingress name, namespace, labels, annotations
    - spec: Ingress specification (rules, TLS config, backend)
    - status: Current status (load balancer ingress)
    
    EXAMPLE USAGE:
    - List Ingresses: list_ingresses_in_namespace(namespace="default")
    - Check routes: list_ingresses_in_namespace(namespace="production")
    """
    try:
        _, apps_v1, _ = get_k8s_clients(cluster_context)
        
        # Ingresses are in networking.k8s.io/v1
        from kubernetes.client import NetworkingV1Api
        networking_v1 = NetworkingV1Api(api_client=apps_v1.api_client)
        
        ingresses = networking_v1.list_namespaced_ingress(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(ing) for ing in ingresses.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Ingresses in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_istio_gateways(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Istio Gateways in a specific namespace.
    
    PURPOSE:
    This tool retrieves Istio Gateway resources, which configure load balancers operating
    at the edge of the mesh to receive incoming or outgoing HTTP/TCP connections. Gateways
    are used to manage ingress/egress traffic for the service mesh.
    
    WHEN TO USE:
    - Reviewing ingress/egress configurations
    - Checking TLS settings for mesh entry points
    - Troubleshooting external traffic routing
    - Auditing mesh boundary configurations
    - Verifying server ports and protocols
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete Gateway metadata including:
    - metadata: Gateway name, namespace, labels, annotations
    - spec: Gateway specification (selector, servers with ports and TLS)
    
    EXAMPLE USAGE:
    - List Gateways: list_istio_gateways(namespace="istio-system")
    - Check ingress gateways: list_istio_gateways(namespace="production")
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "networking.istio.io"
        plural = "gateways"
        versions = ["v1beta1", "v1alpha3"]
        
        for version in versions:
            try:
                gateways = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return gateways.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "Istio Gateway CRD not found",
            "details": "Istio may not be installed or Gateway CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Gateways in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_istio_service_entries(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Istio ServiceEntries in a specific namespace.
    
    PURPOSE:
    This tool retrieves Istio ServiceEntry resources, which enable services within the
    mesh to access external services or add additional entries into Istio's internal
    service registry. ServiceEntries are crucial for mesh-external service integration.
    
    WHEN TO USE:
    - Reviewing external service integrations
    - Checking mesh-external service configurations
    - Troubleshooting external service access
    - Auditing service registry entries
    - Verifying endpoint and resolution configurations
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete ServiceEntry metadata including:
    - metadata: ServiceEntry name, namespace, labels, annotations
    - spec: ServiceEntry specification (hosts, ports, location, resolution, endpoints)
    
    EXAMPLE USAGE:
    - List ServiceEntries: list_istio_service_entries(namespace="default")
    - Check external services: list_istio_service_entries(namespace="production")
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "networking.istio.io"
        plural = "serviceentries"
        versions = ["v1beta1", "v1alpha3"]
        
        for version in versions:
            try:
                service_entries = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return service_entries.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "Istio ServiceEntry CRD not found",
            "details": "Istio may not be installed or ServiceEntry CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list ServiceEntries in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_istio_peer_authentications(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Istio PeerAuthentication policies in a specific namespace.
    
    PURPOSE:
    This tool retrieves Istio PeerAuthentication resources, which define how traffic
    will be tunneled (or not) to the sidecar proxy. PeerAuthentication policies
    control mutual TLS (mTLS) settings for service-to-service communication.
    
    WHEN TO USE:
    - Reviewing mTLS configurations
    - Checking authentication policies
    - Troubleshooting service-to-service auth issues
    - Auditing security policies
    - Verifying permissive/strict mTLS modes
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete PeerAuthentication metadata including:
    - metadata: PeerAuthentication name, namespace, labels, annotations
    - spec: PeerAuthentication specification (selector, mTLS mode, port-level mTLS)
    
    EXAMPLE USAGE:
    - List PeerAuthentications: list_istio_peer_authentications(namespace="default")
    - Check mTLS policies: list_istio_peer_authentications(namespace="production")
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "security.istio.io"
        plural = "peerauthentications"
        versions = ["v1beta1", "v1"]
        
        for version in versions:
            try:
                peer_auths = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return peer_auths.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "Istio PeerAuthentication CRD not found",
            "details": "Istio may not be installed or PeerAuthentication CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list PeerAuthentications in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_istio_authorization_policies(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Istio AuthorizationPolicy resources in a specific namespace.
    
    PURPOSE:
    This tool retrieves Istio AuthorizationPolicy resources, which define access control
    policies for workloads in the mesh. These policies enable workload-level and
    operation-level access control with flexible rule matching.
    
    WHEN TO USE:
    - Reviewing access control policies
    - Checking authorization rules and conditions
    - Troubleshooting access denied issues
    - Auditing security policies
    - Verifying RBAC configurations
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete AuthorizationPolicy metadata including:
    - metadata: AuthorizationPolicy name, namespace, labels, annotations
    - spec: AuthorizationPolicy specification (selector, action, rules with from/to/when)
    
    EXAMPLE USAGE:
    - List AuthorizationPolicies: list_istio_authorization_policies(namespace="default")
    - Check access policies: list_istio_authorization_policies(namespace="production")
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "security.istio.io"
        plural = "authorizationpolicies"
        versions = ["v1beta1", "v1"]
        
        for version in versions:
            try:
                auth_policies = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return auth_policies.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "Istio AuthorizationPolicy CRD not found",
            "details": "Istio may not be installed or AuthorizationPolicy CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list AuthorizationPolicies in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def get_pod_logs(
    pod_name: str,
    namespace: str,
    container: Optional[str] = None,
    tail_lines: int = 100,
    cluster_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get logs from a specific pod.
    
    PURPOSE:
    This tool retrieves logs from a pod's containers, which is essential for
    debugging, monitoring, and troubleshooting application issues.
    
    WHEN TO USE:
    - Debugging application errors
    - Investigating pod crashes or restarts
    - Monitoring application output
    - Troubleshooting startup issues
    
    PARAMETERS:
    - pod_name (required, str): Name of the pod
    - namespace (required, str): Namespace containing the pod
    - container (optional, str): Specific container name (uses first container if not specified)
    - tail_lines (optional, int): Number of lines from the end of logs (default: 100)
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A dictionary containing:
    - pod_name: Name of the pod
    - namespace: Namespace
    - container: Container name
    - logs: Log content as string
    
    EXAMPLE USAGE:
    - Get pod logs: get_pod_logs(pod_name="my-pod", namespace="default")
    - Get specific container: get_pod_logs(pod_name="my-pod", namespace="default", container="app")
    - Get last 50 lines: get_pod_logs(pod_name="my-pod", namespace="default", tail_lines=50)
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        
        logs = core_v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            container=container,
            tail_lines=tail_lines
        )
        
        return {
            "pod_name": pod_name,
            "namespace": namespace,
            "container": container or "default",
            "tail_lines": tail_lines,
            "logs": logs
        }
    except ApiException as e:
        return {
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "pod_name": pod_name,
            "namespace": namespace
        }
    except Exception as e:
        return {
            "error": f"Failed to get logs for pod {pod_name}: {str(e)}",
            "pod_name": pod_name,
            "namespace": namespace
        }


@mcp.tool()
def list_gateways_summary(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Kubernetes Gateway API Gateways in a namespace with SUMMARY information (lightweight).
    
    PURPOSE:
    Returns essential Gateway information for quick overview. This is the PREFERRED tool
    for listing Gateways as it returns only key fields: name, namespace, listener count, status.
    Gateway API is the next-generation ingress/egress API for Kubernetes.
    
    WHEN TO USE:
    - User asks to "list gateways", "show gateways" (DEFAULT CHOICE)
    - Getting overview of ingress/egress configurations
    - Checking Gateway health and listener count
    - Any query NOT requiring full Gateway specifications
    
    USE list_gateways (detailed) ONLY when user asks for "detailed", "full", "yaml" information
    or needs complete listener configurations, TLS settings, or addresses.
    
    PARAMETERS:
    - namespace (required, str): Kubernetes namespace name
    - cluster_context (optional, str): Cluster context from kubeconfig
    
    RETURNS:
    List of dictionaries with essential Gateway info:
    - name: Gateway name
    - namespace: Gateway namespace
    - gateway_class: GatewayClass name
    - listeners: Number of listeners configured
    - addresses: List of assigned addresses (if available)
    - status: Gateway status conditions summary
    
    EXAMPLE RETURN:
    [
        {
            "name": "prod-gateway",
            "namespace": "default",
            "gateway_class": "istio",
            "listeners": 2,
            "addresses": ["10.0.1.5"],
            "status": "Ready"
        }
    ]
    
    NOTE:
    Gateway API must be installed in the cluster. This tool checks v1, v1beta1, and v1alpha2 versions.
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "gateway.networking.k8s.io"
        plural = "gateways"
        versions = ["v1", "v1beta1", "v1alpha2"]
        
        for version in versions:
            try:
                gateways = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                
                summary_list = []
                for gw in gateways.get('items', []):
                    metadata = gw.get('metadata', {})
                    spec = gw.get('spec', {})
                    status = gw.get('status', {})
                    
                    # Extract listeners count
                    listeners = spec.get('listeners', [])
                    listeners_count = len(listeners)
                    
                    # Extract addresses
                    addresses = []
                    for addr in status.get('addresses', []):
                        if 'value' in addr:
                            addresses.append(addr['value'])
                    
                    # Determine status
                    conditions = status.get('conditions', [])
                    gateway_status = "Unknown"
                    for cond in conditions:
                        if cond.get('type') == 'Accepted' or cond.get('type') == 'Ready':
                            if cond.get('status') == 'True':
                                gateway_status = "Ready"
                            else:
                                gateway_status = cond.get('reason', 'NotReady')
                            break
                    
                    summary_list.append({
                        "name": metadata.get('name'),
                        "namespace": metadata.get('namespace'),
                        "gateway_class": spec.get('gatewayClassName'),
                        "listeners": listeners_count,
                        "addresses": addresses,
                        "status": gateway_status
                    })
                
                return summary_list
                
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "Gateway API CRD not found",
            "details": "Gateway API may not be installed or Gateway CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Gateways in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_gateways(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Kubernetes Gateway API Gateways in a namespace with DETAILED information.
    
    PURPOSE:
    Returns FULL Gateway specifications including all listeners, TLS configs, addresses, and conditions.
    Use list_gateways_summary for most queries.
    
    WHEN TO USE DETAILED VERSION:
    - User explicitly asks for "detailed", "full", "yaml", "complete" information
    - Deep debugging of Gateway configurations
    - Need full listener configurations including TLS settings
    - Troubleshooting Gateway routing or certificate issues
    
    FOR NORMAL QUERIES, USE list_gateways_summary INSTEAD.
    
    PARAMETERS:
    - namespace (required, str): Kubernetes namespace name
    - cluster_context (optional, str): Cluster context from kubeconfig
    
    RETURNS:
    List of complete Gateway objects including:
    - apiVersion, kind, metadata
    - spec: gatewayClassName, listeners (with protocol, port, TLS, hostname)
    - status: addresses, conditions, listeners status
    
    NOTE:
    Gateway API must be installed. Checks v1, v1beta1, and v1alpha2 versions.
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "gateway.networking.k8s.io"
        plural = "gateways"
        versions = ["v1", "v1beta1", "v1alpha2"]
        
        for version in versions:
            try:
                gateways = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return gateways.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "Gateway API CRD not found",
            "details": "Gateway API may not be installed or Gateway CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Gateways in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_httproutes_summary(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Kubernetes Gateway API HTTPRoutes in a namespace with SUMMARY information (lightweight).
    
    PURPOSE:
    Returns essential HTTPRoute information for quick overview. This is the PREFERRED tool
    for listing HTTPRoutes as it returns only key fields: name, hostnames, parent refs, rules count.
    HTTPRoutes define HTTP routing rules for Gateway API.
    
    WHEN TO USE:
    - User asks to "list httproutes", "show routes", "show http routes" (DEFAULT CHOICE)
    - Getting overview of HTTP routing configurations
    - Checking route associations with Gateways
    - Any query NOT requiring full route rules and filters
    
    USE list_httproutes (detailed) ONLY when user asks for "detailed", "full", "yaml" information
    or needs complete route rules, matches, filters, or backend configurations.
    
    PARAMETERS:
    - namespace (required, str): Kubernetes namespace name
    - cluster_context (optional, str): Cluster context from kubeconfig
    
    RETURNS:
    List of dictionaries with essential HTTPRoute info:
    - name: HTTPRoute name
    - namespace: HTTPRoute namespace
    - hostnames: List of hostnames this route matches
    - parent_refs: Number of parent Gateway references
    - rules: Number of routing rules configured
    - status: Route status summary
    
    EXAMPLE RETURN:
    [
        {
            "name": "my-app-route",
            "namespace": "default",
            "hostnames": ["api.example.com", "www.example.com"],
            "parent_refs": 1,
            "rules": 3,
            "status": "Accepted"
        }
    ]
    
    NOTE:
    Gateway API must be installed. Checks v1, v1beta1, and v1alpha2 versions.
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "gateway.networking.k8s.io"
        plural = "httproutes"
        versions = ["v1", "v1beta1", "v1alpha2"]
        
        for version in versions:
            try:
                httproutes = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                
                summary_list = []
                for route in httproutes.get('items', []):
                    metadata = route.get('metadata', {})
                    spec = route.get('spec', {})
                    status = route.get('status', {})
                    
                    # Extract hostnames
                    hostnames = spec.get('hostnames', [])
                    
                    # Count parent refs
                    parent_refs = len(spec.get('parentRefs', []))
                    
                    # Count rules
                    rules_count = len(spec.get('rules', []))
                    
                    # Determine status
                    route_status = "Unknown"
                    for parent_status in status.get('parents', []):
                        conditions = parent_status.get('conditions', [])
                        for cond in conditions:
                            if cond.get('type') == 'Accepted':
                                if cond.get('status') == 'True':
                                    route_status = "Accepted"
                                else:
                                    route_status = cond.get('reason', 'NotAccepted')
                                break
                        if route_status != "Unknown":
                            break
                    
                    summary_list.append({
                        "name": metadata.get('name'),
                        "namespace": metadata.get('namespace'),
                        "hostnames": hostnames,
                        "parent_refs": parent_refs,
                        "rules": rules_count,
                        "status": route_status
                    })
                
                return summary_list
                
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "HTTPRoute API CRD not found",
            "details": "Gateway API may not be installed or HTTPRoute CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list HTTPRoutes in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_httproutes(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Kubernetes Gateway API HTTPRoutes in a namespace with DETAILED information.
    
    PURPOSE:
    Returns FULL HTTPRoute specifications including all rules, matches, filters, and backend refs.
    Use list_httproutes_summary for most queries.
    
    WHEN TO USE DETAILED VERSION:
    - User explicitly asks for "detailed", "full", "yaml", "complete" information
    - Deep debugging of HTTP routing configurations
    - Need complete route rules with matches and filters
    - Troubleshooting backend service routing or header manipulation
    - Analyzing path matching, header matching, or query param matching
    
    FOR NORMAL QUERIES, USE list_httproutes_summary INSTEAD.
    
    PARAMETERS:
    - namespace (required, str): Kubernetes namespace name
    - cluster_context (optional, str): Cluster context from kubeconfig
    
    RETURNS:
    List of complete HTTPRoute objects including:
    - apiVersion, kind, metadata
    - spec: hostnames, parentRefs, rules (with matches, filters, backendRefs)
    - status: parents status with conditions
    
    ROUTE FEATURES EXPOSED:
    - Path matching (exact, prefix, regex)
    - Header matching
    - Query parameter matching
    - Request/response header modification
    - Request redirects and rewrites
    - Traffic splitting across backends
    - Timeouts and retry policies
    
    NOTE:
    Gateway API must be installed. Checks v1, v1beta1, and v1alpha2 versions.
    """
    try:
        _, _, custom_api = get_k8s_clients(cluster_context)
        
        group = "gateway.networking.k8s.io"
        plural = "httproutes"
        versions = ["v1", "v1beta1", "v1alpha2"]
        
        for version in versions:
            try:
                httproutes = custom_api.list_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural
                )
                return httproutes.get('items', [])
            except ApiException as e:
                if e.status == 404:
                    continue
                else:
                    raise
        
        return [{
            "error": "HTTPRoute API CRD not found",
            "details": "Gateway API may not be installed or HTTPRoute CRD is not available",
            "namespace": namespace
        }]
        
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list HTTPRoutes in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


@mcp.tool()
def list_events_in_namespace(
    namespace: str,
    cluster_context: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all Events in a specific namespace.
    
    PURPOSE:
    This tool retrieves Kubernetes Event resources, which provide insight into what
    is happening inside the cluster, such as decisions made by scheduler, reasons
    for pod failures, or image pull errors.
    
    WHEN TO USE:
    - Troubleshooting pod scheduling issues
    - Investigating resource problems
    - Checking recent cluster activities
    - Debugging deployment failures
    - Monitoring system warnings and errors
    
    PARAMETERS:
    - namespace (required, str): The Kubernetes namespace to query.
    - cluster_context (optional, str): The name of the cluster context to query.
      
    RETURNS:
    A list of dictionaries containing complete Event metadata including:
    - metadata: Event name, namespace, creation timestamp
    - involved_object: Reference to the object this event is about
    - reason: Short machine-readable reason
    - message: Human-readable description
    - type: Event type (Normal, Warning)
    
    EXAMPLE USAGE:
    - List events: list_events_in_namespace(namespace="default")
    - Check system events: list_events_in_namespace(namespace="kube-system")
    """
    try:
        core_v1, _, _ = get_k8s_clients(cluster_context)
        events = core_v1.list_namespaced_event(namespace=namespace, watch=False)
        
        return [serialize_k8s_object(event) for event in events.items]
    except ApiException as e:
        return [{
            "error": f"Kubernetes API error: {e.status} - {e.reason}",
            "details": e.body,
            "namespace": namespace
        }]
    except Exception as e:
        return [{
            "error": f"Failed to list Events in namespace {namespace}: {str(e)}",
            "namespace": namespace
        }]


def set_default_context(context: str):
    """
    Set the default cluster context for the server.
    
    Args:
        context: Context name to set as default
    """
    cluster_config.default_context = context


def run_server():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    run_server()

