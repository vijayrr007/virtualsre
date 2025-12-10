#!/usr/bin/env python
"""Interactive chat with your Kubernetes cluster using OpenAI.

This provides a conversational interface where you can ask questions
about your cluster in natural language and get intelligent responses.
"""

import os
import sys
from kubernetes import config as k8s_config
from kubernetes.client import CoreV1Api, AppsV1Api, CustomObjectsApi


def setup_kubernetes():
    """Initialize Kubernetes connection."""
    try:
        k8s_config.load_kube_config()
        return True
    except Exception as e:
        print(f"❌ Failed to connect to Kubernetes: {e}")
        return False


def get_kubernetes_data(query_lower):
    """Get relevant Kubernetes data based on the query."""
    try:
        core_v1 = CoreV1Api()
        apps_v1 = AppsV1Api()
        
        data = {}
        
        # Determine what data to fetch based on query
        if "namespace" in query_lower:
            namespaces = core_v1.list_namespace(watch=False)
            data["namespaces"] = [ns.metadata.name for ns in namespaces.items]
        
        if "pod" in query_lower:
            # Check if specific namespace mentioned
            namespace = extract_namespace(query_lower)
            if namespace:
                pods = core_v1.list_namespaced_pod(namespace=namespace, watch=False)
                data["pods"] = [
                    {
                        "name": p.metadata.name,
                        "namespace": p.metadata.namespace,
                        "phase": p.status.phase,
                        "ready": all(c.ready for c in (p.status.container_statuses or []))
                    }
                    for p in pods.items
                ]
            else:
                pods = core_v1.list_pod_for_all_namespaces(watch=False)
                data["pods"] = [
                    {
                        "name": p.metadata.name,
                        "namespace": p.metadata.namespace,
                        "phase": p.status.phase
                    }
                    for p in pods.items[:20]  # Limit to 20 for performance
                ]
        
        if "node" in query_lower:
            nodes = core_v1.list_node(watch=False)
            data["nodes"] = [
                {
                    "name": n.metadata.name,
                    "ready": any(
                        c.type == "Ready" and c.status == "True"
                        for c in n.status.conditions
                    )
                }
                for n in nodes.items
            ]
        
        if "deployment" in query_lower:
            namespace = extract_namespace(query_lower) or "default"
            deployments = apps_v1.list_namespaced_deployment(namespace=namespace, watch=False)
            data["deployments"] = [
                {
                    "name": d.metadata.name,
                    "namespace": d.metadata.namespace,
                    "replicas": d.spec.replicas,
                    "ready": d.status.ready_replicas or 0
                }
                for d in deployments.items
            ]
        
        if "service" in query_lower:
            namespace = extract_namespace(query_lower) or "default"
            services = core_v1.list_namespaced_service(namespace=namespace, watch=False)
            data["services"] = [
                {
                    "name": s.metadata.name,
                    "namespace": s.metadata.namespace,
                    "type": s.spec.type,
                    "cluster_ip": s.spec.cluster_ip
                }
                for s in services.items
            ]
        
        if "event" in query_lower:
            namespace = extract_namespace(query_lower) or "default"
            events = core_v1.list_namespaced_event(namespace=namespace, watch=False)
            data["events"] = [
                {
                    "type": e.type,
                    "reason": e.reason,
                    "message": e.message[:100]
                }
                for e in events.items[:10]  # Last 10 events
            ]
        
        # If query is general (health, status, overview), get summary
        if any(word in query_lower for word in ["health", "status", "overview", "cluster"]):
            if not data:  # Only if we haven't fetched specific data
                namespaces = core_v1.list_namespace(watch=False)
                nodes = core_v1.list_node(watch=False)
                pods = core_v1.list_pod_for_all_namespaces(watch=False)
                
                data["summary"] = {
                    "namespaces": len(namespaces.items),
                    "nodes": len(nodes.items),
                    "total_pods": len(pods.items),
                    "running_pods": sum(1 for p in pods.items if p.status.phase == "Running")
                }
        
        return data
        
    except Exception as e:
        return {"error": str(e)}


def extract_namespace(query):
    """Extract namespace from query."""
    words = query.split()
    
    # Look for namespace after "in"
    if "in" in words:
        idx = words.index("in")
        if idx + 1 < len(words):
            return words[idx + 1].strip("',\"")
    
    # Common namespaces
    for ns in ["default", "kube-system", "production", "staging", "development", "prod", "dev"]:
        if ns in query:
            return "kube-system" if ns == "system" else ns
    
    return None


def chat_with_openai(query, k8s_data, conversation_history):
    """Send query and Kubernetes data to OpenAI for natural language response.
    
    Args:
        query: User's question
        k8s_data: Kubernetes cluster data
        conversation_history: List of previous messages for context
        
    Returns:
        Assistant's response
    """
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "❌ OPENAI_API_KEY not set. Please set it with: export OPENAI_API_KEY='sk-...'"
        
        client = OpenAI(api_key=api_key)
        
        # Build context for OpenAI
        context = f"Current Kubernetes cluster data: {k8s_data}"
        
        # Build messages with conversation history
        messages = [
            {
                "role": "system",
                "content": """You are a helpful Kubernetes SRE assistant. 
Provide clear, conversational responses about the cluster.
Be concise but informative. Highlight any issues or important status.
If asked about health, summarize the overall state.
Use friendly, natural language.
Remember the conversation context and refer back to previous questions when relevant."""
            }
        ]
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current query
        messages.append({
            "role": "user",
            "content": f"{query}\n\n{context}"
        })
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=400
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        return f"❌ Error calling OpenAI: {e}\n\nRaw data: {k8s_data}"


def main():
    """Run interactive chat."""
    print("=" * 70)
    print("🤖 Kubernetes Cluster Chat (Powered by OpenAI)")
    print("=" * 70)
    print()
    
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not set!")
        print()
        print("Please set your OpenAI API key:")
        print("   export OPENAI_API_KEY='sk-...'")
        print()
        return 1
    
    print("✅ OpenAI API key found")
    
    # Connect to Kubernetes
    print("🔌 Connecting to Kubernetes cluster...")
    if not setup_kubernetes():
        return 1
    
    print("✅ Connected to cluster")
    print()
    print("=" * 70)
    print("Ask me anything about your Kubernetes cluster!")
    print("Type 'quit', 'exit', or 'q' to stop.")
    print("Type 'clear' to clear conversation memory.")
    print("=" * 70)
    print()
    
    # Initialize conversation history
    conversation_history = []
    
    # Chat loop
    while True:
        try:
            # Get user input
            query = input("🤔 You: ").strip()
            
            # Check for exit commands
            if query.lower() in ['quit', 'exit', 'q', '']:
                print()
                print("👋 Goodbye! Have a great day!")
                break
            
            # Check for clear command
            if query.lower() == 'clear':
                conversation_history = []
                print("🧹 Conversation memory cleared!")
                print()
                continue
            
            # Get Kubernetes data
            print("💭 Thinking...")
            k8s_data = get_kubernetes_data(query.lower())
            
            # Get OpenAI response with conversation history
            response = chat_with_openai(query, k8s_data, conversation_history)
            
            # Add to conversation history
            conversation_history.append({
                "role": "user",
                "content": query
            })
            conversation_history.append({
                "role": "assistant",
                "content": response
            })
            
            # Keep only last 10 exchanges (20 messages) to avoid token limits
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]
            
            print(f"🤖 Assistant: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\n")
            print("👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

