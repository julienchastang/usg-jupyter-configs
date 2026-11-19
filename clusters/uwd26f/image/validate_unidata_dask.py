"""Validate the classroom DaskCluster spec without a Kubernetes connection."""

from unidata_dask import NODE_SELECTOR, RESOURCES, _make_cluster_spec


def main():
    first = _make_cluster_spec("test-cluster-{uuid}", 0)
    second = _make_cluster_spec("test-cluster-{uuid}", 0)

    assert first["apiVersion"] == "kubernetes.dask.org/v1"
    assert first["kind"] == "DaskCluster"
    assert first["metadata"]["name"] != second["metadata"]["name"]

    for component in ("scheduler", "worker"):
        pod_spec = first["spec"][component]["spec"]
        assert pod_spec["nodeSelector"] == NODE_SELECTOR
        assert pod_spec["containers"][0]["resources"] == RESOURCES

    assert first["spec"]["worker"]["replicas"] == 0
    print("DaskCluster specification is valid")


if __name__ == "__main__":
    main()
