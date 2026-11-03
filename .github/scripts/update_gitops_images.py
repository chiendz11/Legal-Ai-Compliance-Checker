#!/usr/bin/env python3
"""Update image tags in GitOps for Cloud Production and Local k3d deployment."""

import argparse
import json
import sys
from pathlib import Path

import yaml


def update_gitops_images(
    gitops_dir: Path,
    registry: str,
    tag: str,
) -> bool:
    """Update container image overrides in environments/local/apps/kustomization.yaml."""
    kustomize_path = gitops_dir / "environments/local/apps/kustomization.yaml"
    if not kustomize_path.is_file():
        print(f"Error: {kustomize_path} does not exist.", file=sys.stderr)
        return False

    with open(kustomize_path) as f:
        data = yaml.safe_load(f) or {}

    resources = data.get("resources", [])
    backend_res = "../../../workloads/backend"
    if backend_res not in resources:
        resources.append(backend_res)
    frontend_res = "../../../workloads/frontend"
    if frontend_res not in resources:
        resources.append(frontend_res)
    data["resources"] = resources

    target_backend_image = f"{registry}/legal-ai-compliance-checker-backend"
    target_frontend_image = f"{registry}/legal-ai-compliance-checker-frontend"
    images = data.get("images", [])

    # Update backend image
    backend_match = (
        "registry.invalid/legal-checker/backend",
        "legal-backend",
        target_backend_image,
    )
    found_backend = False
    for entry in images:
        if entry.get("name") in backend_match:
            entry["name"] = target_backend_image
            entry["newTag"] = tag
            entry.pop("newName", None)
            found_backend = True
            break
    if not found_backend:
        images.append(
            {
                "name": target_backend_image,
                "newTag": tag,
            }
        )

    # Update frontend image
    frontend_match = (
        "registry.invalid/legal-checker/frontend",
        "legal-frontend",
        target_frontend_image,
    )
    found_frontend = False
    for entry in images:
        if entry.get("name") in frontend_match:
            entry["name"] = target_frontend_image
            entry["newTag"] = tag
            entry.pop("newName", None)
            found_frontend = True
            break
    if not found_frontend:
        images.append(
            {
                "name": target_frontend_image,
                "newTag": tag,
            }
        )

    data["images"] = images

    # Ensure configMapGenerator is present
    if "configMapGenerator" not in data:
        data["configMapGenerator"] = [
            {
                "name": "legal-backend-config",
                "literals": [
                    "SOURCE_CACHE_DIR=/cache/source",
                    "SOURCE_DOWNLOAD_TIMEOUT_SECONDS=30",
                    "SOURCE_MAX_BYTES=104857600",
                    "PYTHONDONTWRITEBYTECODE=1",
                ],
            }
        ]

    with open(kustomize_path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    print(
        f"Updated {kustomize_path} with {target_backend_image}:{tag} "
        f"and {target_frontend_image}:{tag}"
    )

    # Also update release.json if present
    release_path = gitops_dir / "environments/local/apps/release.json"
    if release_path.is_file():
        try:
            with open(release_path) as f:
                rel = json.load(f)
            rel["backend_enabled"] = True
            rel["image"] = f"{target_backend_image}:{tag}"
            rel["frontend_enabled"] = True
            rel["frontend_image"] = f"{target_frontend_image}:{tag}"
            with open(release_path, "w") as f:
                json.dump(rel, f, indent=2)
                f.write("\n")
            print(f"Updated {release_path}")
        except Exception as e:
            print(f"Warning: failed to update release.json: {e}")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update image tags in Legal-Ai-Compliance-Checker-gitops"
    )
    parser.add_argument(
        "--gitops-dir",
        type=Path,
        required=True,
        help="Path to Legal-Ai-Compliance-Checker-gitops repository root",
    )
    parser.add_argument(
        "--registry",
        default="ghcr.io/chiendz11",
        help="Container registry prefix (default: ghcr.io/chiendz11)",
    )
    parser.add_argument(
        "--tag",
        required=True,
        help="Image tag to apply (e.g. sha-2b34c16 or latest)",
    )
    args = parser.parse_args()

    success = update_gitops_images(
        gitops_dir=args.gitops_dir,
        registry=args.registry.rstrip("/"),
        tag=args.tag,
    )
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
