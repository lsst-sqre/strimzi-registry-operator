"""Tests for the Kopf handlers and operator startup."""

import importlib
from collections.abc import Iterator
from typing import Any
from unittest.mock import Mock

import kopf
import pytest
from kubernetes.client.exceptions import ApiException

from strimziregistryoperator import handlers, startup, state
from strimziregistryoperator.handlers import createregistry, secretwatcher


def call_handler(handler: Any, **kwargs: Any) -> Any:
    return handler(**kwargs)


@pytest.fixture(autouse=True)
def reset_registry_state() -> Iterator[None]:
    original_cluster_name = state.cluster_name
    original_registry_names = set(state.registry_names)
    state.registry_names.clear()
    yield
    state.cluster_name = original_cluster_name
    state.registry_names.clear()
    state.registry_names.update(original_registry_names)


def test_handler_import_does_not_access_kubernetes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_k8sclient = Mock()
    monkeypatch.setattr(startup, "create_k8sclient", create_k8sclient)

    importlib.reload(handlers)

    create_k8sclient.assert_not_called()


def test_start_operator_filters_registry_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    state.registry_names.add("stale")
    api = Mock()
    api.list_namespaced_custom_object.return_value = {
        "items": [
            {
                "metadata": {
                    "name": "matching",
                    "labels": {"strimzi.io/cluster": "events"},
                }
            },
            {
                "metadata": {
                    "name": "different",
                    "labels": {"strimzi.io/cluster": "other"},
                }
            },
            {"metadata": {"name": "unlabeled"}},
        ]
    }
    k8s_client = Mock()
    k8s_client.CustomObjectsApi.return_value = api
    monkeypatch.setattr(startup, "create_k8sclient", lambda: k8s_client)

    call_handler(startup.start_operator, logger=Mock())

    assert state.registry_names == {"matching"}


def test_create_registry_for_matching_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    create_registry_resources = Mock()
    k8s_client = Mock()
    monkeypatch.setattr(
        createregistry,
        "create_registry_resources",
        create_registry_resources,
    )
    monkeypatch.setattr(createregistry, "create_k8sclient", lambda: k8s_client)

    call_handler(
        createregistry.create_registry,
        spec={},
        meta={},
        namespace="events",
        name="registry",
        uid="12345",
        logger=Mock(),
        body={"metadata": {"labels": {"strimzi.io/cluster": "events"}}},
    )

    create_registry_resources.assert_called_once()
    assert state.registry_names == {"registry"}


def test_create_registry_ignores_different_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    create_k8sclient = Mock()
    monkeypatch.setattr(createregistry, "create_k8sclient", create_k8sclient)

    call_handler(
        createregistry.create_registry,
        spec={},
        meta={},
        namespace="events",
        name="registry",
        uid="12345",
        logger=Mock(),
        body={"metadata": {"labels": {"strimzi.io/cluster": "other"}}},
    )

    create_k8sclient.assert_not_called()
    assert state.registry_names == set()


def test_create_registry_rejects_missing_cluster_label() -> None:
    with pytest.raises(kopf.PermanentError):
        call_handler(
            createregistry.create_registry,
            spec={},
            meta={},
            namespace="events",
            name="registry",
            uid="12345",
            logger=Mock(),
            body={"metadata": {}},
        )


def test_delete_registry_removes_cached_name() -> None:
    state.registry_names.add("registry")

    call_handler(createregistry.delete_registry, name="registry")

    assert state.registry_names == set()


def test_parse_registry_spec_group_id() -> None:
    custom = createregistry.parse_registry_spec(
        {"groupId": "custom-registry-group"}, "registry", Mock()
    )
    default = createregistry.parse_registry_spec({}, "registry", Mock())

    assert custom["registry_group_id"] == "custom-registry-group"
    assert default["registry_group_id"] == "schema-registry"


@pytest.mark.parametrize(("spec", "expected"), [({}, 2), ({"replicas": 1}, 1)])
def test_parse_registry_spec_replicas(
    spec: dict[str, int], expected: int
) -> None:
    config = createregistry.parse_registry_spec(spec, "registry", Mock())

    assert config["registry_replicas"] == expected


@pytest.mark.parametrize("replicas", [0, -1])
def test_parse_registry_spec_rejects_invalid_replicas(replicas: int) -> None:
    with pytest.raises(kopf.PermanentError, match="at least one replica"):
        createregistry.parse_registry_spec(
            {"replicas": replicas}, "registry", Mock()
        )


@pytest.mark.parametrize(
    ("spec", "expected_group_id"),
    [
        ({"groupId": "custom-registry-group"}, "custom-registry-group"),
        ({}, "schema-registry"),
    ],
)
def test_update_registry_group_id(
    spec: dict[str, str],
    expected_group_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    k8s_client = Mock()
    update_deployment_group_id = Mock()
    monkeypatch.setattr(createregistry, "create_k8sclient", lambda: k8s_client)
    monkeypatch.setattr(
        createregistry,
        "update_deployment_group_id",
        update_deployment_group_id,
    )

    call_handler(
        createregistry.update_registry_group_id,
        spec=spec,
        namespace="events",
        name="registry",
        logger=Mock(),
        body={"metadata": {"labels": {"strimzi.io/cluster": "events"}}},
    )

    update_deployment_group_id.assert_called_once_with(
        group_id=expected_group_id,
        k8s_client=k8s_client,
        name="registry",
        namespace="events",
    )


def test_update_registry_group_id_ignores_different_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    create_k8sclient = Mock()
    monkeypatch.setattr(createregistry, "create_k8sclient", create_k8sclient)

    call_handler(
        createregistry.update_registry_group_id,
        spec={"groupId": "custom-registry-group"},
        namespace="events",
        name="registry",
        logger=Mock(),
        body={"metadata": {"labels": {"strimzi.io/cluster": "other"}}},
    )

    create_k8sclient.assert_not_called()


def test_update_registry_group_id_rejects_missing_cluster_label() -> None:
    with pytest.raises(kopf.PermanentError):
        call_handler(
            createregistry.update_registry_group_id,
            spec={"groupId": "custom-registry-group"},
            namespace="events",
            name="registry",
            logger=Mock(),
            body={"metadata": {}},
        )


@pytest.mark.parametrize("replicas", [1, 2])
def test_update_registry_replicas(
    replicas: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    state.cluster_name = "events"
    k8s_client = Mock()
    logger = Mock()
    body = {"metadata": {"labels": {"strimzi.io/cluster": "events"}}}
    calls: list[str] = []
    update_deployment_replicas = Mock(
        side_effect=lambda **kwargs: calls.append("deployment")
    )
    reconcile_pod_disruption_budget = Mock(
        side_effect=lambda **kwargs: calls.append("pdb")
    )
    monkeypatch.setattr(createregistry, "create_k8sclient", lambda: k8s_client)
    monkeypatch.setattr(
        createregistry,
        "update_deployment_replicas",
        update_deployment_replicas,
    )
    monkeypatch.setattr(
        createregistry,
        "reconcile_pod_disruption_budget",
        reconcile_pod_disruption_budget,
    )

    call_handler(
        createregistry.update_registry_replicas,
        spec={"replicas": replicas},
        namespace="events",
        name="registry",
        logger=logger,
        body=body,
    )

    update_deployment_replicas.assert_called_once_with(
        replicas=replicas,
        k8s_client=k8s_client,
        name="registry",
        namespace="events",
    )
    reconcile_pod_disruption_budget.assert_called_once_with(
        replicas=replicas,
        name="registry",
        namespace="events",
        k8s_client=k8s_client,
        body=body,
        logger=logger,
    )
    assert calls == ["deployment", "pdb"]


def test_update_registry_replicas_ignores_different_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    create_k8sclient = Mock()
    monkeypatch.setattr(createregistry, "create_k8sclient", create_k8sclient)

    call_handler(
        createregistry.update_registry_replicas,
        spec={"replicas": 2},
        namespace="events",
        name="registry",
        logger=Mock(),
        body={"metadata": {"labels": {"strimzi.io/cluster": "other"}}},
    )

    create_k8sclient.assert_not_called()


def test_update_registry_replicas_rejects_missing_cluster_label() -> None:
    with pytest.raises(kopf.PermanentError):
        call_handler(
            createregistry.update_registry_replicas,
            spec={"replicas": 2},
            namespace="events",
            name="registry",
            logger=Mock(),
            body={"metadata": {}},
        )


def test_update_registry_replicas_propagates_deployment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    monkeypatch.setattr(createregistry, "create_k8sclient", Mock())
    monkeypatch.setattr(
        createregistry,
        "update_deployment_replicas",
        Mock(side_effect=ApiException(status=500)),
    )
    reconcile_pod_disruption_budget = Mock()
    monkeypatch.setattr(
        createregistry,
        "reconcile_pod_disruption_budget",
        reconcile_pod_disruption_budget,
    )

    with pytest.raises(ApiException) as excinfo:
        call_handler(
            createregistry.update_registry_replicas,
            spec={"replicas": 2},
            namespace="events",
            name="registry",
            logger=Mock(),
            body={"metadata": {"labels": {"strimzi.io/cluster": "events"}}},
        )

    assert excinfo.value.status == 500
    reconcile_pod_disruption_budget.assert_not_called()


@pytest.mark.parametrize("invalid_registry", ["missing", "different"])
def test_cluster_ca_rotation_skips_untracked_registry(
    invalid_registry: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    state.registry_names.update({"active", invalid_registry})
    k8s_client = Mock()
    create_secret = Mock(return_value={"metadata": {"name": "active-jks"}})
    update_deployment = Mock()

    def get_ssr(
        *, name: str, namespace: str, k8s_client: Any
    ) -> dict[str, Any]:
        if name == "missing":
            raise ApiException(status=404)
        cluster = "other" if name == "different" else "events"
        return {"metadata": {"labels": {"strimzi.io/cluster": cluster}}}

    monkeypatch.setattr(secretwatcher, "create_k8sclient", lambda: k8s_client)
    monkeypatch.setattr(secretwatcher, "get_ssr", get_ssr)
    monkeypatch.setattr(secretwatcher, "create_secret", create_secret)
    monkeypatch.setattr(
        secretwatcher,
        "get_secret",
        Mock(return_value={"metadata": {"resourceVersion": "12345"}}),
    )
    monkeypatch.setattr(
        secretwatcher, "get_deployment", Mock(return_value=Mock())
    )
    monkeypatch.setattr(secretwatcher, "update_deployment", update_deployment)

    secretwatcher.refresh_with_new_cluster_ca(
        cluster_ca_secret={
            "metadata": {"labels": {"strimzi.io/cluster": "events"}}
        },
        namespace="events",
        logger=Mock(),
    )

    assert state.registry_names == {"active"}
    create_secret.assert_called_once()
    update_deployment.assert_called_once()


def test_cluster_ca_rotation_propagates_api_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    state.registry_names.add("registry")
    monkeypatch.setattr(secretwatcher, "create_k8sclient", Mock())
    monkeypatch.setattr(
        secretwatcher,
        "get_ssr",
        Mock(side_effect=ApiException(status=500)),
    )

    with pytest.raises(ApiException) as excinfo:
        secretwatcher.refresh_with_new_cluster_ca(
            cluster_ca_secret={
                "metadata": {"labels": {"strimzi.io/cluster": "events"}}
            },
            namespace="events",
            logger=Mock(),
        )

    assert excinfo.value.status == 500
    assert state.registry_names == {"registry"}


@pytest.mark.parametrize("registry_state", ["missing", "different"])
def test_client_secret_rotation_skips_untracked_registry(
    registry_state: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    state.registry_names.add("registry")
    create_secret = Mock()
    if registry_state == "missing":
        get_ssr = Mock(side_effect=ApiException(status=404))
    else:
        get_ssr = Mock(
            return_value={
                "metadata": {"labels": {"strimzi.io/cluster": "other"}}
            }
        )
    monkeypatch.setattr(secretwatcher, "create_k8sclient", Mock())
    monkeypatch.setattr(secretwatcher, "get_ssr", get_ssr)
    monkeypatch.setattr(secretwatcher, "create_secret", create_secret)

    secretwatcher.refresh_with_new_client_secret(
        kafkauser_secret={
            "metadata": {
                "name": "registry",
                "labels": {"strimzi.io/cluster": "events"},
            }
        },
        namespace="events",
        logger=Mock(),
    )

    assert state.registry_names == set()
    create_secret.assert_not_called()


def mock_registry_resource_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Mock, Mock, Mock, Mock]:
    k8s_client = Mock()
    get_deployment = Mock()
    get_pod_disruption_budget = Mock()
    get_service = Mock()
    monkeypatch.setattr(
        createregistry,
        "get_kafka_bootstrap_server",
        Mock(return_value="kafka:9093"),
    )
    monkeypatch.setattr(
        createregistry,
        "create_secret",
        Mock(return_value={"metadata": {"name": "registry-jks"}}),
    )
    monkeypatch.setattr(
        createregistry,
        "get_secret",
        Mock(return_value={"metadata": {"resourceVersion": "12345"}}),
    )
    monkeypatch.setattr(createregistry, "get_deployment", get_deployment)
    monkeypatch.setattr(
        createregistry,
        "get_pod_disruption_budget",
        get_pod_disruption_budget,
    )
    monkeypatch.setattr(createregistry, "get_service", get_service)
    monkeypatch.setattr(kopf, "adopt", Mock())
    return (
        k8s_client,
        get_deployment,
        get_pod_disruption_budget,
        get_service,
    )


def registry_body() -> dict[str, Any]:
    return {
        "apiVersion": "roundtable.lsst.codes/v1beta1",
        "kind": "StrimziSchemaRegistry",
        "metadata": {
            "name": "registry",
            "namespace": "events",
            "uid": "12345",
            "labels": {"strimzi.io/cluster": "events"},
        },
    }


def registry_config(*, replicas: int = 2) -> dict[str, Any]:
    return {
        "registry_image": "confluentinc/cp-schema-registry",
        "registry_image_tag": "8.0.0",
        "registry_replicas": replicas,
        "registry_cpu_limit": None,
        "registry_cpu_request": None,
        "registry_mem_limit": None,
        "registry_mem_request": None,
        "registry_compatibility_level": "forward",
        "security_protocol": "SSL",
        "registry_topic": "registry-schemas",
        "registry_group_id": "schema-registry",
        "service_type": "ClusterIP",
    }


def create_registry_resources(k8s_client: Mock, *, replicas: int = 2) -> None:
    createregistry.create_registry_resources(
        name="registry",
        namespace="events",
        strimzi_api_version="v1beta2",
        listener_name="tls",
        k8s_client=k8s_client,
        body=registry_body(),
        logger=Mock(),
        config=registry_config(replicas=replicas),
    )


@pytest.mark.parametrize(
    ("replicas", "pdb_state"),
    [(1, "present"), (1, "missing"), (2, "missing"), (2, "present")],
)
def test_resume_registry_reconciles_availability(
    replicas: int,
    pdb_state: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state.cluster_name = "events"
    k8s_client, _, get_pod_disruption_budget, _ = (
        mock_registry_resource_dependencies(monkeypatch)
    )
    if pdb_state == "missing":
        get_pod_disruption_budget.side_effect = ApiException(status=404)
    update_deployment_replicas = Mock()
    monkeypatch.setattr(createregistry, "create_k8sclient", lambda: k8s_client)
    monkeypatch.setattr(
        createregistry,
        "update_deployment_replicas",
        update_deployment_replicas,
    )

    call_handler(
        createregistry.resume_registry,
        spec={"replicas": replicas},
        namespace="events",
        name="registry",
        logger=Mock(),
        body=registry_body(),
    )

    update_deployment_replicas.assert_called_once_with(
        replicas=replicas,
        k8s_client=k8s_client,
        name="registry",
        namespace="events",
    )
    policy_api = k8s_client.PolicyV1Api.return_value
    if replicas == 1 and pdb_state == "present":
        policy_api.delete_namespaced_pod_disruption_budget.assert_called_once_with(
            name="registry", namespace="events"
        )
        policy_api.create_namespaced_pod_disruption_budget.assert_not_called()
    elif replicas >= 2 and pdb_state == "missing":
        policy_api.create_namespaced_pod_disruption_budget.assert_called_once()
        policy_api.delete_namespaced_pod_disruption_budget.assert_not_called()
    else:
        policy_api.create_namespaced_pod_disruption_budget.assert_not_called()
        policy_api.delete_namespaced_pod_disruption_budget.assert_not_called()


def test_existing_registry_resources_are_not_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, _, _, _ = mock_registry_resource_dependencies(monkeypatch)

    create_registry_resources(k8s_client)

    k8s_client.AppsV1Api.return_value.create_namespaced_deployment.assert_not_called()
    k8s_client.PolicyV1Api.return_value.create_namespaced_pod_disruption_budget.assert_not_called()
    k8s_client.CoreV1Api.return_value.create_namespaced_service.assert_not_called()


def test_missing_registry_resources_are_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, get_deployment, get_pod_disruption_budget, get_service = (
        mock_registry_resource_dependencies(monkeypatch)
    )
    get_deployment.side_effect = ApiException(status=404)
    get_pod_disruption_budget.side_effect = ApiException(status=404)
    get_service.side_effect = ApiException(status=404)

    create_registry_resources(k8s_client)

    k8s_client.AppsV1Api.return_value.create_namespaced_deployment.assert_called_once()
    k8s_client.PolicyV1Api.return_value.create_namespaced_pod_disruption_budget.assert_called_once()
    k8s_client.CoreV1Api.return_value.create_namespaced_service.assert_called_once()


def test_missing_pod_disruption_budget_is_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, _, get_pod_disruption_budget, _ = (
        mock_registry_resource_dependencies(monkeypatch)
    )
    get_pod_disruption_budget.side_effect = ApiException(status=404)

    create_registry_resources(k8s_client)

    k8s_client.AppsV1Api.return_value.create_namespaced_deployment.assert_not_called()
    k8s_client.PolicyV1Api.return_value.create_namespaced_pod_disruption_budget.assert_called_once()
    k8s_client.CoreV1Api.return_value.create_namespaced_service.assert_not_called()


def test_single_replica_registry_has_no_pod_disruption_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, _, get_pod_disruption_budget, _ = (
        mock_registry_resource_dependencies(monkeypatch)
    )
    get_pod_disruption_budget.side_effect = ApiException(status=404)

    create_registry_resources(k8s_client, replicas=1)

    policy_api = k8s_client.PolicyV1Api.return_value
    policy_api.create_namespaced_pod_disruption_budget.assert_not_called()
    policy_api.delete_namespaced_pod_disruption_budget.assert_not_called()


def test_single_replica_registry_removes_pod_disruption_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, _, _, _ = mock_registry_resource_dependencies(monkeypatch)

    create_registry_resources(k8s_client, replicas=1)

    k8s_client.PolicyV1Api.return_value.delete_namespaced_pod_disruption_budget.assert_called_once_with(
        name="registry", namespace="events"
    )


def test_pod_disruption_budget_delete_ignores_missing_resource(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, _, _, _ = mock_registry_resource_dependencies(monkeypatch)
    policy_api = k8s_client.PolicyV1Api.return_value
    policy_api.delete_namespaced_pod_disruption_budget.side_effect = (
        ApiException(status=404)
    )

    create_registry_resources(k8s_client, replicas=1)


def test_pod_disruption_budget_delete_errors_are_propagated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, _, _, _ = mock_registry_resource_dependencies(monkeypatch)
    policy_api = k8s_client.PolicyV1Api.return_value
    policy_api.delete_namespaced_pod_disruption_budget.side_effect = (
        ApiException(status=500)
    )

    with pytest.raises(ApiException) as excinfo:
        create_registry_resources(k8s_client, replicas=1)

    assert excinfo.value.status == 500


@pytest.mark.parametrize(
    ("resource", "error"),
    [
        ("deployment", ApiException(status=403)),
        ("deployment", RuntimeError("deployment lookup failed")),
        ("pod disruption budget", ApiException(status=500)),
        (
            "pod disruption budget",
            RuntimeError("pod disruption budget lookup failed"),
        ),
        ("service", ApiException(status=500)),
        ("service", RuntimeError("service lookup failed")),
    ],
)
def test_registry_resource_lookup_errors_are_propagated(
    resource: str,
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    k8s_client, get_deployment, get_pod_disruption_budget, get_service = (
        mock_registry_resource_dependencies(monkeypatch)
    )
    if resource == "deployment":
        get_deployment.side_effect = error
    elif resource == "pod disruption budget":
        get_pod_disruption_budget.side_effect = error
    else:
        get_service.side_effect = error

    with pytest.raises(type(error)):
        create_registry_resources(k8s_client)

    k8s_client.AppsV1Api.return_value.create_namespaced_deployment.assert_not_called()
    k8s_client.PolicyV1Api.return_value.create_namespaced_pod_disruption_budget.assert_not_called()
    k8s_client.CoreV1Api.return_value.create_namespaced_service.assert_not_called()
