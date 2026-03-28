import pathlib
import subprocess
import time

import pytest
import requests
from kubernetes import client, config

NAMESPACE = "test-agent-sandbox"
RELEASE_NAME = "test-router"
DEPLOYMENT_NAME = "sandbox-router-deployment"
GATEWAY_URL = "https://test-router.lab.linuxdweller.com"

_TESTS_DIR = pathlib.Path(__file__).parent
_CHART_DIR = _TESTS_DIR.parent


@pytest.fixture(scope="session")
def k8s_apps_v1():
    config.load_kube_config()
    return client.AppsV1Api()


@pytest.fixture(scope="session", autouse=True)
def helm_release():
    _helm_uninstall()
    _helm_upgrade_install()
    yield
    _helm_uninstall()


def _helm_upgrade_install():
    subprocess.run(
        [
            "helm",
            "upgrade",
            "--create-namespace",
            "--install",
            RELEASE_NAME,
            str(_CHART_DIR),
            "--namespace",
            NAMESPACE,
            "--values",
            str(_TESTS_DIR / "values.yaml"),
            "--wait",
            "--timeout",
            "120s",
        ],
        check=True,
    )


def _helm_uninstall():
    subprocess.run(
        [
            "helm",
            "uninstall",
            RELEASE_NAME,
            "--namespace",
            NAMESPACE,
            "--wait",
            "--timeout",
            "60s",
        ],
        check=False,  # ignore if release does not exist
    )


def test_deployment_ready(k8s_apps_v1):
    deadline = time.monotonic() + 60
    while True:
        print("checking deployment status...")
        deploy = k8s_apps_v1.read_namespaced_deployment(
            name=DEPLOYMENT_NAME,
            namespace=NAMESPACE,
        )
        desired = deploy.spec.replicas or 1
        ready = deploy.status.ready_replicas or 0
        print(f"got desired replicas: {desired}, ready replicas: {ready}")
        if ready >= desired:
            return
        if time.monotonic() >= deadline:
            pytest.fail(
                f"deployment not ready within 60s: ready={ready}, desired={desired}"
            )
        time.sleep(1)


def test_httproute_healthz():
    resp = requests.get(f"{GATEWAY_URL}/healthz")
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}"
