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
