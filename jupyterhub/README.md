# jupyterhub config

This directory holds the JupyterHub-side integration config required by `nblaunch`.

## Source of truth

- `jupyterhub/values-nblaunch.yaml` is the only Hub-side source of truth in this repository.
- It is the file intended to be passed to the JupyterHub Helm chart.
- It contains the `nblaunch` service registration, role bindings, and inline `extraConfig` snippets.

The standalone `nblaunch` service code, tests, manifests, and service-local docs were migrated to a separate repository. This repository now owns only the Hub-side wiring.

## Rollout checklist

1. Merge the secret token values into your uncommitted Helm secrets file so they override the placeholders in `jupyterhub/values-nblaunch.yaml`.
2. Add `--values jupyterhub/values-nblaunch.yaml` to your `helm upgrade --install ...` command for the Hub.
3. Confirm the inline home volume mount selector assumptions in `jupyterhub/values-nblaunch.yaml`:
   - volume name `home`
   - mount path `/home/jovyan`
4. Confirm the `NBLAUNCH_SERVICE_TOKEN` value injected into the standalone `nblaunch` Deployment matches the token supplied to the Hub through `jupyterhub/values-nblaunch.yaml`.
5. Roll out Hub changes before or alongside the `nblaunch` Deployment update.

## Verification

After rollout, confirm:
- the Hub exposes the `nblaunch` service route and OAuth callback path
- the `nblaunch` service can call the home-subpath API with its service token
- the pre-spawn hook mutates only the intended home volume mount
- the same username maps to the same subpath in Hub and `nblaunch`

## Rollback

1. Revert the Hub changes in `jupyterhub/values-nblaunch.yaml` if spawn behavior or user-home mapping is wrong.
2. Revert the standalone `nblaunch` Deployment if the Hub config remains correct but the service behavior regressed.

No environment-specific overlay is required in this repository snapshot because the service registration uses service-local identifiers and token references rather than committed production hostnames or secrets.
