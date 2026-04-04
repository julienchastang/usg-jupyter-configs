from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NBLAUNCH_VALUES = ROOT / "jupyterhub" / "values-nblaunch.yaml"


def test_nblaunch_service_registration_is_coherent() -> None:
    text = NBLAUNCH_VALUES.read_text(encoding="utf-8")

    assert "services:" in text
    assert "nblaunch:" in text
    assert "url: http://nblaunch:8000" in text
    assert "oauth_client_id: service-nblaunch" in text
    assert "oauth_redirect_uri: /services/nblaunch/oauth_callback" in text
    assert 'NBLAUNCH_SERVICE_TOKEN: "set-this-in-secrets-values"' in text
    assert 'apiToken: "set-this-in-secrets-values"' in text


def test_nblaunch_role_scopes_match_the_service_registration() -> None:
    text = NBLAUNCH_VALUES.read_text(encoding="utf-8")

    assert "loadRoles:" in text
    assert "nblaunch-service:" in text
    assert "- access:services!service=nblaunch" in text
    assert "- read:users:name" in text
    assert "services:\n        - nblaunch" in text


def test_nblaunch_inline_extra_config_contains_expected_hooks() -> None:
    text = NBLAUNCH_VALUES.read_text(encoding="utf-8")

    assert "extraConfig:" in text
    assert "21-home-subpath.py: |" in text
    assert 'HOME_SUBPATH_PREFIX = "users"' in text
    assert 'HOME_VOLUME_NAME = "home"' in text
    assert 'HOME_MOUNT_PATH = "/home/jovyan"' in text
    assert "c.KubeSpawner.pre_spawn_hook = make_nblaunch_pre_spawn_hook(" in text
    assert "22-nblaunch-home-subpath-api.py: |" in text
    assert "class NBLaunchHomeSubpathHandler(web.RequestHandler):" in text
    assert "only the nblaunch service may read home-subpath mappings" in text
    assert r'r"/services/nblaunch/home-subpath/(?P<username>[^/]+)"' in text
