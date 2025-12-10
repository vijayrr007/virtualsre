"""Verify local Kubernetes cluster connectivity.

This script checks if you can connect to your local Kubernetes cluster
and verifies that the MCP server will work with it.
"""

import asyncio
import sys
from kubernetes import config as k8s_config
from kubernetes.client import CoreV1Api
from mcp_client import create_client


def check_kubectl_config():
    """Check if kubeconfig is accessible."""
    print("=" * 60)
    print("Step 1: Checking kubeconfig file")
    print("=" * 60)
    
    try:
        contexts, active_context = k8s_config.list_kube_config_contexts()
        
        print(f"✅ Kubeconfig found!")
        print(f"   Current context: {active_context['name']}")
        print(f"\n   Available contexts:")
        for ctx in contexts:
            marker = " ← (active)" if ctx['name'] == active_context['name'] else ""
            print(f"     - {ctx['name']}{marker}")
        
        return True, active_context['name']
    except Exception as e:
        print(f"❌ Error reading kubeconfig: {e}")
        print("\n   Possible solutions:")
        print("   1. Make sure kubectl is installed: brew install kubectl")
        print("   2. Check if kubeconfig exists: ls -la ~/.kube/config")
        print("   3. If using Docker Desktop, enable Kubernetes in preferences")
        print("   4. If using minikube, run: minikube start")
        return False, None


def check_cluster_connectivity(context_name):
    """Check if we can connect to the cluster."""
    print("\n" + "=" * 60)
    print("Step 2: Testing cluster connectivity")
    print("=" * 60)
    
    try:
        k8s_config.load_kube_config(context=context_name)
        v1 = CoreV1Api()
        
        # Try to list namespaces
        namespaces = v1.list_namespace(timeout_seconds=5)
        
        print(f"✅ Successfully connected to cluster!")
        print(f"   Found {len(namespaces.items)} namespaces:")
        for ns in namespaces.items[:5]:  # Show first 5
            print(f"     - {ns.metadata.name}")
        if len(namespaces.items) > 5:
            print(f"     ... and {len(namespaces.items) - 5} more")
        
        return True
    except Exception as e:
        print(f"❌ Error connecting to cluster: {e}")
        print("\n   Possible solutions:")
        print(f"   1. Make sure cluster is running")
        print(f"   2. For Docker Desktop: Check if Kubernetes is started")
        print(f"   3. For minikube: Run 'minikube status'")
        print(f"   4. For kind: Run 'kind get clusters'")
        return False


def check_cluster_resources(context_name):
    """Check what resources are available in the cluster."""
    print("\n" + "=" * 60)
    print("Step 3: Checking available resources")
    print("=" * 60)
    
    try:
        k8s_config.load_kube_config(context=context_name)
        v1 = CoreV1Api()
        
        # Check pods
        pods = v1.list_pod_for_all_namespaces(timeout_seconds=5)
        print(f"✅ Pods: {len(pods.items)} found")
        
        # Check nodes
        nodes = v1.list_node(timeout_seconds=5)
        print(f"✅ Nodes: {len(nodes.items)} found")
        for node in nodes.items:
            status = "Ready" if any(
                c.type == "Ready" and c.status == "True" 
                for c in node.status.conditions
            ) else "NotReady"
            print(f"     - {node.metadata.name}: {status}")
        
        # Check services
        services = v1.list_service_for_all_namespaces(timeout_seconds=5)
        print(f"✅ Services: {len(services.items)} found")
        
        return True
    except Exception as e:
        print(f"⚠️  Error checking resources: {e}")
        return False


async def test_mcp_client(context_name):
    """Test the MCP client with the local cluster."""
    print("\n" + "=" * 60)
    print("Step 4: Testing MCP Client")
    print("=" * 60)
    
    try:
        # Create MCP client
        client = create_client(
            transport="stdio",
            server_script_path="./mcp_server.py"
        )
        
        print("🔄 Starting MCP server...")
        async with client:
            print("✅ MCP server started successfully!")
            
            # Test list_available_contexts
            print("\n   Testing: list_available_contexts()")
            contexts = await client.list_available_contexts()
            print(f"   ✅ Found {len(contexts)} contexts")
            
            # Test list_namespaces
            print("\n   Testing: list_namespaces()")
            namespaces = await client.list_namespaces(cluster_context=context_name)
            if isinstance(namespaces, list) and namespaces:
                if "error" in namespaces[0]:
                    print(f"   ⚠️  Error: {namespaces[0]['error']}")
                else:
                    print(f"   ✅ Successfully listed {len(namespaces)} namespaces")
            
            # Test list_pods_in_namespace
            print("\n   Testing: list_pods_in_namespace('default')")
            pods = await client.list_pods_in_namespace("default", cluster_context=context_name)
            if isinstance(pods, list):
                if pods and "error" in pods[0]:
                    print(f"   ⚠️  Error: {pods[0]['error']}")
                else:
                    print(f"   ✅ Successfully listed {len(pods)} pods in default namespace")
            
            print("\n✅ MCP client is working correctly!")
            return True
            
    except Exception as e:
        print(f"❌ Error testing MCP client: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_istio():
    """Check if Istio is installed."""
    print("\n" + "=" * 60)
    print("Step 5: Checking Istio (Optional)")
    print("=" * 60)
    
    try:
        from kubernetes.client import CustomObjectsApi
        k8s_config.load_kube_config()
        custom_api = CustomObjectsApi()
        
        # Try to list VirtualServices
        try:
            vs = custom_api.list_cluster_custom_object(
                group="networking.istio.io",
                version="v1beta1",
                plural="virtualservices",
                timeout_seconds=5
            )
            print(f"✅ Istio is installed!")
            print(f"   Found {len(vs.get('items', []))} VirtualServices")
        except:
            # Try v1alpha3
            try:
                vs = custom_api.list_cluster_custom_object(
                    group="networking.istio.io",
                    version="v1alpha3",
                    plural="virtualservices",
                    timeout_seconds=5
                )
                print(f"✅ Istio is installed (v1alpha3)!")
                print(f"   Found {len(vs.get('items', []))} VirtualServices")
            except:
                print("ℹ️  Istio is not installed (this is optional)")
                print("   Istio tools will return 'CRD not found' errors")
                print("   All other Kubernetes tools will work fine")
        
    except Exception as e:
        print(f"ℹ️  Could not check Istio status: {e}")


async def main():
    """Run all verification checks."""
    print("\n" + "=" * 70)
    print("VirtualSRE - Local Kubernetes Cluster Verification")
    print("=" * 70)
    print("\nThis script will verify that your local Kubernetes cluster")
    print("is compatible with the VirtualSRE MCP server.\n")
    
    # Step 1: Check kubeconfig
    success, context_name = check_kubectl_config()
    if not success:
        print("\n❌ Cannot proceed without valid kubeconfig")
        sys.exit(1)
    
    # Step 2: Check connectivity
    success = check_cluster_connectivity(context_name)
    if not success:
        print("\n❌ Cannot connect to cluster")
        sys.exit(1)
    
    # Step 3: Check resources
    check_cluster_resources(context_name)
    
    # Step 4: Test MCP client
    success = await test_mcp_client(context_name)
    if not success:
        print("\n⚠️  MCP client test failed")
        sys.exit(1)
    
    # Step 5: Check Istio (optional)
    check_istio()
    
    # Final summary
    print("\n" + "=" * 70)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 70)
    print("\n🎉 Your local Kubernetes cluster is fully compatible!")
    print(f"   Cluster context: {context_name}")
    print("\n📝 Next steps:")
    print("   1. Run the MCP server: python main.py")
    print(f"   2. Or with specific context: python main.py --context {context_name}")
    print("   3. Try examples: python example_usage.py")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Verification interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


