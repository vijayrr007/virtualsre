"""MCP Client for connecting to EKS Cluster MCP Server.

This client supports multiple transport types:
- stdio: Local process communication (default)
- sse: Server-Sent Events for HTTP streaming
- http: HTTP-based request/response with streaming
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, Optional, List, Literal
from abc import ABC, abstractmethod
import httpx
from enum import Enum


class TransportType(str, Enum):
    """Supported transport types."""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class MCPTransport(ABC):
    """Abstract base class for MCP transports."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from the MCP server."""
        pass
    
    @abstractmethod
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        pass


class StdioTransport(MCPTransport):
    """STDIO transport for local process communication."""
    
    def __init__(self, server_script_path: str):
        """
        Initialize STDIO transport.
        
        Args:
            server_script_path: Path to the MCP server Python script
        """
        self.server_script_path = server_script_path
        self.process = None
        self.request_id = 0
    
    async def connect(self) -> bool:
        """Connect to the MCP server via STDIO."""
        try:
            import sys
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,  # Use current Python interpreter
                self.server_script_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            return True
        except Exception as e:
            print(f"Failed to start MCP server process: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None
    
    async def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and receive response."""
        if not self.process:
            raise RuntimeError("Not connected to MCP server")
        
        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from server")
        
        return json.loads(response_line.decode())
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/list",
            "params": {}
        }
        
        response = await self._send_request(request)
        
        if "result" in response:
            return response["result"].get("tools", [])
        elif "error" in response:
            raise RuntimeError(f"Error listing tools: {response['error']}")
        
        return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self._send_request(request)
        
        if "result" in response:
            return response["result"]
        elif "error" in response:
            raise RuntimeError(f"Tool call failed: {response['error']}")
        
        return None


class SSETransport(MCPTransport):
    """Server-Sent Events transport for HTTP streaming."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize SSE transport.
        
        Args:
            base_url: Base URL of the MCP server (e.g., http://localhost:8000)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = None
        self.request_id = 0
    
    async def connect(self) -> bool:
        """Connect to the MCP server via SSE."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
            
            # Test connection
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to connect to MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        if not self.client:
            raise RuntimeError("Not connected to MCP server")
        
        self.request_id += 1
        
        async with self.client.stream(
            "POST",
            "/sse/tools/list",
            json={
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/list",
                "params": {}
            }
        ) as response:
            tools = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "result" in data:
                        tools = data["result"].get("tools", [])
                    elif "error" in data:
                        raise RuntimeError(f"Error listing tools: {data['error']}")
            
            return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with SSE streaming."""
        if not self.client:
            raise RuntimeError("Not connected to MCP server")
        
        self.request_id += 1
        
        async with self.client.stream(
            "POST",
            "/sse/tools/call",
            json={
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
        ) as response:
            result = None
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "result" in data:
                        result = data["result"]
                    elif "error" in data:
                        raise RuntimeError(f"Tool call failed: {data['error']}")
            
            return result


class HTTPTransport(MCPTransport):
    """HTTP transport for request/response communication."""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize HTTP transport.
        
        Args:
            base_url: Base URL of the MCP server (e.g., http://localhost:8000)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.client = None
        self.request_id = 0
    
    async def connect(self) -> bool:
        """Connect to the MCP server via HTTP."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            self.client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=30.0
            )
            
            # Test connection
            response = await self.client.get("/health")
            return response.status_code == 200
        except Exception as e:
            print(f"Failed to connect to MCP server: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        if not self.client:
            raise RuntimeError("Not connected to MCP server")
        
        self.request_id += 1
        
        response = await self.client.post(
            "/api/tools/list",
            json={
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/list",
                "params": {}
            }
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "result" in data:
            return data["result"].get("tools", [])
        elif "error" in data:
            raise RuntimeError(f"Error listing tools: {data['error']}")
        
        return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool."""
        if not self.client:
            raise RuntimeError("Not connected to MCP server")
        
        self.request_id += 1
        
        response = await self.client.post(
            "/api/tools/call",
            json={
                "jsonrpc": "2.0",
                "id": self.request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
        )
        
        response.raise_for_status()
        data = response.json()
        
        if "result" in data:
            return data["result"]
        elif "error" in data:
            raise RuntimeError(f"Tool call failed: {data['error']}")
        
        return None


class EKSMCPClient:
    """
    High-level MCP client for EKS cluster operations.
    
    Supports multiple transport types and provides convenient methods
    for calling EKS cluster tools.
    """
    
    def __init__(
        self,
        transport_type: TransportType = TransportType.STDIO,
        server_script_path: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """
        Initialize EKS MCP client.
        
        Args:
            transport_type: Type of transport to use (stdio, sse, or http)
            server_script_path: Path to server script (required for stdio)
            base_url: Base URL of server (required for sse and http)
            api_key: Optional API key for authentication (for sse and http)
        """
        self.transport_type = transport_type
        
        if transport_type == TransportType.STDIO:
            if not server_script_path:
                raise ValueError("server_script_path required for STDIO transport")
            self.transport = StdioTransport(server_script_path)
        elif transport_type == TransportType.SSE:
            if not base_url:
                raise ValueError("base_url required for SSE transport")
            self.transport = SSETransport(base_url, api_key)
        elif transport_type == TransportType.HTTP:
            if not base_url:
                raise ValueError("base_url required for HTTP transport")
            self.transport = HTTPTransport(base_url, api_key)
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self) -> bool:
        """Connect to the MCP server."""
        return await self.transport.connect()
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        await self.transport.disconnect()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools."""
        return await self.transport.list_tools()
    
    async def list_available_contexts(self) -> List[str]:
        """List available cluster contexts."""
        return await self.transport.call_tool("list_available_contexts", {})
    
    async def list_all_pods(self, cluster_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all pods in the cluster."""
        args = {}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_all_pods", args)
    
    async def list_pods_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List pods in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_pods_in_namespace", args)
    
    async def list_deployments_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List deployments in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_deployments_in_namespace", args)
    
    async def list_services_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List services in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_services_in_namespace", args)
    
    async def list_istio_virtual_services(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Istio VirtualServices in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_istio_virtual_services", args)
    
    async def list_istio_destination_rules(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Istio DestinationRules in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_istio_destination_rules", args)
    
    # Additional Kubernetes resource methods
    
    async def list_namespaces(
        self,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all namespaces in the cluster."""
        args = {}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_namespaces", args)
    
    async def list_nodes(
        self,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all nodes in the cluster."""
        args = {}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_nodes", args)
    
    async def list_configmaps_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List ConfigMaps in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_configmaps_in_namespace", args)
    
    async def list_secrets_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Secrets (metadata only) in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_secrets_in_namespace", args)
    
    async def list_statefulsets_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List StatefulSets in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_statefulsets_in_namespace", args)
    
    async def list_daemonsets_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List DaemonSets in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_daemonsets_in_namespace", args)
    
    async def list_jobs_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Jobs in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_jobs_in_namespace", args)
    
    async def list_cronjobs_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List CronJobs in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_cronjobs_in_namespace", args)
    
    async def list_ingresses_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Ingresses in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_ingresses_in_namespace", args)
    
    async def list_events_in_namespace(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Events in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_events_in_namespace", args)
    
    # Additional Istio resource methods
    
    async def list_istio_gateways(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Istio Gateways in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_istio_gateways", args)
    
    async def list_istio_service_entries(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Istio ServiceEntries in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_istio_service_entries", args)
    
    async def list_istio_peer_authentications(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Istio PeerAuthentication policies in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_istio_peer_authentications", args)
    
    async def list_istio_authorization_policies(
        self,
        namespace: str,
        cluster_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List Istio AuthorizationPolicy resources in a specific namespace."""
        args = {"namespace": namespace}
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("list_istio_authorization_policies", args)
    
    # Utility methods
    
    async def get_pod_logs(
        self,
        pod_name: str,
        namespace: str,
        container: Optional[str] = None,
        tail_lines: int = 100,
        cluster_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get logs from a specific pod."""
        args = {
            "pod_name": pod_name,
            "namespace": namespace,
            "tail_lines": tail_lines
        }
        if container:
            args["container"] = container
        if cluster_context:
            args["cluster_context"] = cluster_context
        return await self.transport.call_tool("get_pod_logs", args)


# Convenience function for quick client creation
def create_client(
    transport: Literal["stdio", "sse", "http"] = "stdio",
    **kwargs
) -> EKSMCPClient:
    """
    Create an EKS MCP client with the specified transport.
    
    Args:
        transport: Transport type ("stdio", "sse", or "http")
        **kwargs: Transport-specific arguments
        
    Returns:
        Configured EKSMCPClient instance
        
    Example:
        # STDIO transport
        client = create_client("stdio", server_script_path="./mcp_server.py")
        
        # SSE transport
        client = create_client("sse", base_url="http://localhost:8000", api_key="secret")
        
        # HTTP transport
        client = create_client("http", base_url="http://localhost:8000")
    """
    return EKSMCPClient(transport_type=TransportType(transport), **kwargs)

