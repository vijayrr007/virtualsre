"""Main entry point for VirtualSRE MCP Server."""

import argparse
import sys
import os
from pathlib import Path
from mcp_server import run_server, set_default_context
from config import ClusterConfig


def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="VirtualSRE MCP Server - EKS Cluster Operations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default kubeconfig
  python main.py

  # Run with custom kubeconfig
  python main.py --kubeconfig /path/to/kubeconfig

  # Run with specific default context
  python main.py --context prod-cluster

  # Run with AWS profile
  python main.py --aws-profile production --aws-region us-west-2

  # List available contexts
  python main.py --list-contexts
        """
    )
    
    parser.add_argument(
        "--kubeconfig",
        type=str,
        default=None,
        help="Path to kubeconfig file (default: ~/.kube/config)"
    )
    
    parser.add_argument(
        "--context",
        type=str,
        default=None,
        help="Default cluster context to use"
    )
    
    parser.add_argument(
        "--aws-profile",
        type=str,
        default=None,
        help="AWS profile name for EKS authentication"
    )
    
    parser.add_argument(
        "--aws-region",
        type=str,
        default=None,
        help="AWS region for EKS clusters (default: us-east-1)"
    )
    
    parser.add_argument(
        "--list-contexts",
        action="store_true",
        help="List available cluster contexts and exit"
    )
    
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "sse", "http"],
        default="stdio",
        help="Transport type to use (default: stdio)"
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to for SSE/HTTP transports (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to for SSE/HTTP transports (default: 8000)"
    )
    
    args = parser.parse_args()
    
    # Initialize cluster configuration
    config = ClusterConfig(
        kubeconfig_path=args.kubeconfig,
        aws_region=args.aws_region,
        aws_profile=args.aws_profile,
        default_context=args.context
    )
    
    # Handle list-contexts command
    if args.list_contexts:
        print("Available cluster contexts:")
        contexts = config.get_available_contexts()
        if contexts:
            for ctx in contexts:
                marker = " (default)" if ctx == config.default_context else ""
                print(f"  - {ctx}{marker}")
        else:
            print("  No contexts found in kubeconfig")
        return 0
    
    # Set default context if provided
    if args.context:
        set_default_context(args.context)
        print(f"Using default context: {args.context}")
    
    # Display server information
    print("=" * 60)
    print("VirtualSRE MCP Server - EKS Cluster Operations")
    print("=" * 60)
    print(f"Transport: {args.transport}")
    
    if args.transport in ["sse", "http"]:
        print(f"Server URL: http://{args.host}:{args.port}")
    
    if config.default_context:
        print(f"Default Context: {config.default_context}")
    
    contexts = config.get_available_contexts()
    if contexts:
        print(f"Available Contexts: {', '.join(contexts)}")
    
    print("=" * 60)
    print("\nServer is ready to accept connections...")
    print("Press Ctrl+C to stop the server\n")
    
    try:
        # Run the MCP server
        run_server()
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
