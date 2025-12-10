"""Example usage of the EKS MCP Client.

This script demonstrates how to use the MCP client to interact with EKS clusters
through the MCP server. It shows examples of all available operations.
"""

import asyncio
import json
from mcp_client import EKSMCPClient, TransportType, create_client


async def example_stdio_transport():
    """Example using STDIO transport (local process)."""
    print("=" * 70)
    print("Example 1: Using STDIO Transport (Local Process)")
    print("=" * 70)
    
    # Create client with STDIO transport
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # List available contexts
        print("\n1. Listing available cluster contexts...")
        contexts = await client.list_available_contexts()
        print(f"Available contexts: {json.dumps(contexts, indent=2)}")
        
        # List all pods
        print("\n2. Listing all pods in the cluster...")
        try:
            pods = await client.list_all_pods()
            print(f"Found {len(pods)} pods")
            if pods:
                # Show first pod as example
                print("\nFirst pod example:")
                print(json.dumps(pods[0], indent=2, default=str))
        except Exception as e:
            print(f"Error: {e}")
        
        # List pods in default namespace
        print("\n3. Listing pods in 'default' namespace...")
        try:
            pods = await client.list_pods_in_namespace("default")
            print(f"Found {len(pods)} pods in default namespace")
            if pods and isinstance(pods, list) and len(pods) > 0:
                pod = pods[0]
                if isinstance(pod, dict) and "metadata" in pod:
                    print(f"Example pod: {pod['metadata'].get('name', 'unknown')}")
        except Exception as e:
            print(f"Error: {e}")
        
        # List deployments
        print("\n4. Listing deployments in 'default' namespace...")
        try:
            deployments = await client.list_deployments_in_namespace("default")
            print(f"Found {len(deployments)} deployments")
            if deployments and isinstance(deployments, list):
                for dep in deployments[:3]:  # Show first 3
                    if isinstance(dep, dict) and "metadata" in dep:
                        name = dep['metadata'].get('name', 'unknown')
                        replicas = dep.get('status', {}).get('replicas', 'N/A')
                        print(f"  - {name} (replicas: {replicas})")
        except Exception as e:
            print(f"Error: {e}")
        
        # List services
        print("\n5. Listing services in 'default' namespace...")
        try:
            services = await client.list_services_in_namespace("default")
            print(f"Found {len(services)} services")
            if services and isinstance(services, list):
                for svc in services[:3]:  # Show first 3
                    if isinstance(svc, dict) and "metadata" in svc:
                        name = svc['metadata'].get('name', 'unknown')
                        svc_type = svc.get('spec', {}).get('type', 'unknown')
                        print(f"  - {name} (type: {svc_type})")
        except Exception as e:
            print(f"Error: {e}")
        
        # List Istio VirtualServices
        print("\n6. Listing Istio VirtualServices in 'default' namespace...")
        try:
            virtual_services = await client.list_istio_virtual_services("default")
            if virtual_services and isinstance(virtual_services, list):
                if isinstance(virtual_services[0], dict) and "error" in virtual_services[0]:
                    print(f"Note: {virtual_services[0]['error']}")
                else:
                    print(f"Found {len(virtual_services)} VirtualServices")
                    for vs in virtual_services[:3]:
                        if isinstance(vs, dict) and "metadata" in vs:
                            print(f"  - {vs['metadata'].get('name', 'unknown')}")
        except Exception as e:
            print(f"Error: {e}")
        
        # List Istio DestinationRules
        print("\n7. Listing Istio DestinationRules in 'default' namespace...")
        try:
            dest_rules = await client.list_istio_destination_rules("default")
            if dest_rules and isinstance(dest_rules, list):
                if isinstance(dest_rules[0], dict) and "error" in dest_rules[0]:
                    print(f"Note: {dest_rules[0]['error']}")
                else:
                    print(f"Found {len(dest_rules)} DestinationRules")
                    for dr in dest_rules[:3]:
                        if isinstance(dr, dict) and "metadata" in dr:
                            print(f"  - {dr['metadata'].get('name', 'unknown')}")
        except Exception as e:
            print(f"Error: {e}")


async def example_sse_transport():
    """Example using SSE transport (Server-Sent Events)."""
    print("\n\n" + "=" * 70)
    print("Example 2: Using SSE Transport (HTTP Streaming)")
    print("=" * 70)
    print("\nNote: This requires the MCP server to be running with SSE support.")
    print("Start the server with: python main.py --transport sse --port 8000")
    
    try:
        # Create client with SSE transport
        client = create_client(
            transport="sse",
            base_url="http://localhost:8000",
            api_key=None  # Add API key if authentication is required
        )
        
        async with client:
            print("\nConnected to MCP server via SSE")
            
            # List pods in kube-system namespace
            print("\nListing pods in 'kube-system' namespace...")
            pods = await client.list_pods_in_namespace("kube-system")
            print(f"Found {len(pods)} system pods")
            
    except Exception as e:
        print(f"\nCould not connect via SSE: {e}")
        print("Make sure the server is running with SSE transport enabled.")


async def example_http_transport():
    """Example using HTTP transport."""
    print("\n\n" + "=" * 70)
    print("Example 3: Using HTTP Transport")
    print("=" * 70)
    print("\nNote: This requires the MCP server to be running with HTTP support.")
    print("Start the server with: python main.py --transport http --port 8000")
    
    try:
        # Create client with HTTP transport
        client = create_client(
            transport="http",
            base_url="http://localhost:8000",
            api_key=None  # Add API key if authentication is required
        )
        
        async with client:
            print("\nConnected to MCP server via HTTP")
            
            # List services in kube-system namespace
            print("\nListing services in 'kube-system' namespace...")
            services = await client.list_services_in_namespace("kube-system")
            print(f"Found {len(services)} system services")
            
    except Exception as e:
        print(f"\nCould not connect via HTTP: {e}")
        print("Make sure the server is running with HTTP transport enabled.")


async def example_multi_cluster():
    """Example working with multiple clusters."""
    print("\n\n" + "=" * 70)
    print("Example 4: Multi-Cluster Operations")
    print("=" * 70)
    
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # Get available contexts
        print("\n1. Getting available cluster contexts...")
        contexts = await client.list_available_contexts()
        print(f"Available contexts: {contexts}")
        
        if not contexts or len(contexts) == 0:
            print("\nNo cluster contexts found. Please configure kubeconfig.")
            return
        
        # Query each cluster
        print("\n2. Querying pods from each cluster...")
        for context in contexts[:2]:  # Limit to first 2 contexts
            print(f"\n  Context: {context}")
            try:
                pods = await client.list_all_pods(cluster_context=context)
                if isinstance(pods, list):
                    print(f"    Total pods: {len(pods)}")
            except Exception as e:
                print(f"    Error: {e}")


async def example_error_handling():
    """Example demonstrating error handling."""
    print("\n\n" + "=" * 70)
    print("Example 5: Error Handling")
    print("=" * 70)
    
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # Try to access non-existent namespace
        print("\n1. Trying to access non-existent namespace...")
        try:
            pods = await client.list_pods_in_namespace("non-existent-namespace-12345")
            if isinstance(pods, list) and len(pods) == 0:
                print("   Result: Empty list (namespace might not exist or has no pods)")
            elif isinstance(pods, list) and pods and "error" in pods[0]:
                print(f"   Error: {pods[0]['error']}")
        except Exception as e:
            print(f"   Exception caught: {e}")
        
        # Try to access with invalid context
        print("\n2. Trying to use invalid cluster context...")
        try:
            pods = await client.list_all_pods(cluster_context="invalid-context-xyz")
            if isinstance(pods, list) and pods and "error" in pods[0]:
                print(f"   Error: {pods[0]['error']}")
        except Exception as e:
            print(f"   Exception caught: {e}")


async def example_istio_operations():
    """Example focused on Istio service mesh operations."""
    print("\n\n" + "=" * 70)
    print("Example 6: Istio Service Mesh Operations")
    print("=" * 70)
    print("\nNote: This requires Istio to be installed in the cluster.")
    
    client = create_client(
        transport="stdio",
        server_script_path="./mcp_server.py"
    )
    
    async with client:
        # Check istio-system namespace
        namespace = "istio-system"
        
        print(f"\n1. Checking Istio components in '{namespace}' namespace...")
        try:
            pods = await client.list_pods_in_namespace(namespace)
            if isinstance(pods, list) and not (pods and "error" in pods[0]):
                print(f"   Found {len(pods)} Istio system pods")
                for pod in pods[:5]:
                    if isinstance(pod, dict) and "metadata" in pod:
                        name = pod['metadata'].get('name', 'unknown')
                        phase = pod.get('status', {}).get('phase', 'unknown')
                        print(f"     - {name}: {phase}")
        except Exception as e:
            print(f"   Error: {e}")
        
        print(f"\n2. Listing VirtualServices in '{namespace}'...")
        try:
            vs_list = await client.list_istio_virtual_services(namespace)
            if isinstance(vs_list, list) and vs_list and "error" in vs_list[0]:
                print(f"   {vs_list[0]['error']}")
            else:
                print(f"   Found {len(vs_list)} VirtualServices")
        except Exception as e:
            print(f"   Error: {e}")
        
        print(f"\n3. Listing DestinationRules in '{namespace}'...")
        try:
            dr_list = await client.list_istio_destination_rules(namespace)
            if isinstance(dr_list, list) and dr_list and "error" in dr_list[0]:
                print(f"   {dr_list[0]['error']}")
            else:
                print(f"   Found {len(dr_list)} DestinationRules")
        except Exception as e:
            print(f"   Error: {e}")


async def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("EKS MCP Client - Example Usage")
    print("=" * 70)
    print("\nThis script demonstrates various ways to use the EKS MCP client.")
    print("\nPrerequisites:")
    print("  - Valid kubeconfig file (~/.kube/config)")
    print("  - At least one configured cluster context")
    print("  - (Optional) Istio installed for service mesh examples")
    
    try:
        # Run STDIO examples (always available)
        await example_stdio_transport()
        
        # Run multi-cluster example
        await example_multi_cluster()
        
        # Run error handling example
        await example_error_handling()
        
        # Run Istio example
        await example_istio_operations()
        
        # SSE and HTTP examples (require server to be running separately)
        print("\n\n" + "=" * 70)
        print("Network Transport Examples (SSE and HTTP)")
        print("=" * 70)
        print("\nTo test SSE and HTTP transports, start the server in a separate terminal:")
        print("  python main.py --transport sse --port 8000")
        print("or")
        print("  python main.py --transport http --port 8000")
        print("\nThen run these examples:")
        # await example_sse_transport()
        # await example_http_transport()
        
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
    except Exception as e:
        print(f"\n\nError running examples: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n\n" + "=" * 70)
    print("Examples Complete")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())


