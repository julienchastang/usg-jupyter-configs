"""Dask Kubernetes cluster configuration for the UWD26F classroom."""

import getpass
import uuid

from dask_kubernetes.operator import KubeCluster, make_cluster_spec


NAMESPACE = "jhub"
IMAGE = "unidata/uwd26f:2026Nov22_022953_d433"
NODE_SELECTOR = {"capi.stackhpc.com/node-group": "mediums"}
RESOURCES = {
    "requests": {"cpu": "1", "memory": "2Gi"},
    "limits": {"cpu": "2", "memory": "3Gi"},
}


def _make_cluster_spec(name, workers):
    name = name.format(user=getpass.getuser(), uuid=str(uuid.uuid4())[:10])
    spec = make_cluster_spec(
        name=name,
        image=IMAGE,
        n_workers=workers,
        resources=RESOURCES,
    )
    spec["spec"]["scheduler"]["spec"]["nodeSelector"] = NODE_SELECTOR
    spec["spec"]["worker"]["spec"]["nodeSelector"] = NODE_SELECTOR
    return spec


def create_cluster(name="my-dask-cluster-{uuid}", workers=0):
    """Create a classroom Dask cluster on the autoscaling compute nodes."""
    return KubeCluster(
        namespace=NAMESPACE,
        custom_cluster_spec=_make_cluster_spec(name, workers),
        resource_timeout=300,
    )
