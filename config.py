"""Configuration management for EKS cluster connections."""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
from kubernetes import config as k8s_config
from kubernetes.client import Configuration
import boto3


class ClusterConfig:
    """Manages EKS cluster connection configuration."""
    
    def __init__(
        self,
        kubeconfig_path: Optional[str] = None,
        aws_region: Optional[str] = None,
        aws_profile: Optional[str] = None,
        default_context: Optional[str] = None
    ):
        """
        Initialize cluster configuration.
        
        Args:
            kubeconfig_path: Path to kubeconfig file (default: ~/.kube/config)
            aws_region: AWS region for EKS clusters
            aws_profile: AWS profile name for authentication
            default_context: Default cluster context to use
        """
        self.kubeconfig_path = kubeconfig_path or os.path.expanduser("~/.kube/config")
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-east-1")
        self.aws_profile = aws_profile or os.getenv("AWS_PROFILE")
        self.default_context = default_context
        self._contexts = {}
        self._load_contexts()
    
    def _load_contexts(self):
        """Load available contexts from kubeconfig."""
        try:
            if os.path.exists(self.kubeconfig_path):
                with open(self.kubeconfig_path, 'r') as f:
                    kubeconfig = yaml.safe_load(f)
                    contexts = kubeconfig.get('contexts', [])
                    for ctx in contexts:
                        name = ctx.get('name')
                        if name:
                            self._contexts[name] = ctx
        except Exception as e:
            print(f"Warning: Could not load kubeconfig: {e}")
    
    def get_available_contexts(self) -> List[str]:
        """
        Get list of available cluster contexts.
        
        Returns:
            List of context names
        """
        return list(self._contexts.keys())
    
    def load_kube_config(self, context: Optional[str] = None) -> Configuration:
        """
        Load Kubernetes configuration for specified context.
        
        Args:
            context: Cluster context name (uses default if not specified)
            
        Returns:
            Kubernetes Configuration object
            
        Raises:
            Exception: If configuration cannot be loaded
        """
        context = context or self.default_context
        
        try:
            # Try loading from kubeconfig file
            if os.path.exists(self.kubeconfig_path):
                k8s_config.load_kube_config(
                    config_file=self.kubeconfig_path,
                    context=context
                )
                return k8s_config.new_client_from_config(
                    config_file=self.kubeconfig_path,
                    context=context
                )
        except Exception as kubeconfig_error:
            # Fallback to AWS EKS authentication
            try:
                return self._load_eks_config(context)
            except Exception as eks_error:
                raise Exception(
                    f"Failed to load config from kubeconfig: {kubeconfig_error}. "
                    f"Failed to load EKS config: {eks_error}"
                )
    
    def _load_eks_config(self, cluster_name: Optional[str]) -> Configuration:
        """
        Load Kubernetes configuration using AWS EKS authentication.
        
        Args:
            cluster_name: EKS cluster name
            
        Returns:
            Kubernetes Configuration object
            
        Raises:
            Exception: If EKS configuration cannot be loaded
        """
        if not cluster_name:
            raise ValueError("Cluster name required for EKS authentication")
        
        session = boto3.Session(
            profile_name=self.aws_profile,
            region_name=self.aws_region
        )
        
        eks_client = session.client('eks')
        
        # Get cluster information
        cluster_info = eks_client.describe_cluster(name=cluster_name)
        cluster = cluster_info['cluster']
        
        # Create Kubernetes configuration
        configuration = Configuration()
        configuration.host = cluster['endpoint']
        configuration.verify_ssl = True
        configuration.ssl_ca_cert = self._get_ca_cert(cluster)
        
        # Get authentication token
        sts_client = session.client('sts')
        token = self._get_eks_token(cluster_name, sts_client)
        configuration.api_key = {"authorization": f"Bearer {token}"}
        
        return configuration
    
    def _get_ca_cert(self, cluster: Dict[str, Any]) -> str:
        """
        Extract and save CA certificate from cluster info.
        
        Args:
            cluster: EKS cluster information
            
        Returns:
            Path to CA certificate file
        """
        import base64
        import tempfile
        
        ca_cert = base64.b64decode(
            cluster['certificateAuthority']['data']
        ).decode('utf-8')
        
        # Save to temporary file
        fd, path = tempfile.mkstemp(suffix='.crt')
        with os.fdopen(fd, 'w') as f:
            f.write(ca_cert)
        
        return path
    
    def _get_eks_token(self, cluster_name: str, sts_client) -> str:
        """
        Generate EKS authentication token.
        
        Args:
            cluster_name: EKS cluster name
            sts_client: boto3 STS client
            
        Returns:
            Authentication token
        """
        from botocore.signers import RequestSigner
        from botocore.model import ServiceId
        import base64
        from datetime import datetime, timedelta
        
        service_id = ServiceId('sts')
        signer = RequestSigner(
            service_id,
            self.aws_region,
            'sts',
            'v4',
            sts_client._request_signer._credentials,
            sts_client._client_config.signature_version
        )
        
        params = {
            'method': 'GET',
            'url': f'https://sts.{self.aws_region}.amazonaws.com/'
                   f'?Action=GetCallerIdentity&Version=2011-06-15',
            'body': {},
            'headers': {
                'x-k8s-aws-id': cluster_name
            },
            'context': {}
        }
        
        signed_url = signer.generate_presigned_url(
            params,
            region_name=self.aws_region,
            expires_in=60,
            operation_name=''
        )
        
        # Create token from signed URL
        token = f'k8s-aws-v1.{base64.urlsafe_b64encode(signed_url.encode()).decode().rstrip("=")}'
        
        return token


def get_default_config() -> ClusterConfig:
    """
    Get default cluster configuration.
    
    Returns:
        ClusterConfig instance with default settings
    """
    return ClusterConfig()


