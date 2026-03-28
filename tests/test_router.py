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
JOB_NAME = "sandbox-client"

_TESTS_DIR = pathlib.Path(__file__).parent
_CHART_DIR = _TESTS_DIR.parent
_EXAMPLE_JOB_MANIFEST = _TESTS_DIR / "example-job.yaml"


@pytest.fixture(scope="session")
def k8s_apps_v1():
    config.load_kube_config()
    return client.AppsV1Api()


@pytest.fixture(scope="session")
def k8s_batch_v1():
    config.load_kube_config()
    return client.BatchV1Api()


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


@pytest.fixture()
def example_job(helm_release):
    subprocess.run(
        ["kubectl", "delete", "job", JOB_NAME, "-n", NAMESPACE, "--ignore-not-found"],
        check=True,
    )
    subprocess.run(
        ["kubectl", "apply", "-f", str(_EXAMPLE_JOB_MANIFEST)],
        check=True,
    )
    yield
    subprocess.run(
        ["kubectl", "delete", "-f", str(_EXAMPLE_JOB_MANIFEST), "--ignore-not-found"],
        check=True,
    )


def test_httproute_healthz():
    resp = requests.get(f"{GATEWAY_URL}/healthz")
    assert resp.status_code == 200, f"expected 200, got {resp.status_code}"


def test_sandbox_client_job(example_job, k8s_batch_v1):
    deadline = time.monotonic() + 360
    while True:
        job = k8s_batch_v1.read_namespaced_job(name=JOB_NAME, namespace=NAMESPACE)
        succeeded = job.status.succeeded or 0
        failed = job.status.failed or 0
        print(f"job status: succeeded={succeeded}, failed={failed}")
        if succeeded >= 1:
            return
        if failed >= 1:
            pytest.fail(f"sandbox client job failed: {job.status}")
        if time.monotonic() >= deadline:
            pytest.fail("sandbox client job did not complete within 120s")
        time.sleep(2)
