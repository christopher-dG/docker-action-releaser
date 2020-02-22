import json
import os
import re
import tarfile
import traceback
import sys

from hashlib import sha1
from io import BytesIO
from tempfile import mkdtemp
from typing import NoReturn

import docker
import yaml

from github import Github, UnknownObjectException
from github.Requester import requests
from semver import VersionInfo

DOCKER_USERNAME = os.getenv("INPUT_DOCKER_USERNAME", "")
DOCKER_PASSWORD = os.getenv("INPUT_DOCKER_PASSWORD", "")
EVENT_NAME = os.getenv("GITHUB_EVENT_NAME", "")
EVENT_PATH = os.getenv("GITHUB_EVENT_PATH", "")
REPO = os.getenv("GITHUB_REPOSITORY", "")
RUN_ID = os.getenv("GITHUB_RUN_ID", "")
TOKEN = os.getenv("INPUT_TOKEN", "")
TRIGGER = os.getenv("INPUT_TRIGGER", "")


class Failure(Exception):
    pass


def ignore(msg: str, status: int = 0) -> NoReturn:
    print(msg)
    sys.exit(status)


def fail(msg: str) -> NoReturn:
    raise Failure(msg)


def main() -> None:
    gh_repo = Github(TOKEN).get_repo(REPO, lazy=True)

    # Validate event
    if EVENT_NAME != "issue_comment":
        ignore("Not an issue comment event")
    with open(EVENT_PATH) as f:
        payload = json.load(f)

    try:
        # Parse comment
        if TRIGGER not in payload["comment"]["body"]:
            ignore("Comment is not a DAR trigger")
        parser = rf"{TRIGGER}\s+(major|minor|patch)(.*)"
        m = re.search(parser, payload["comment"]["body"])
        if not m:
            fail("Comment does not contain a valid version bump")
        bump = m[1].lower()
        changelog = m[2].strip()

        # Check permissions
        perms = gh_repo.get_collaborator_permission(payload["sender"]["login"])
        if perms not in ("admin", "write"):
            fail("You are not allowed to create a release")

        # Download repository
        tar_url = gh_repo.get_archive_link("tarball")
        resp = requests.get(tar_url)
        if resp.status_code != 200:
            fail("Downloading repositoru failed")
        tgz = tarfile.open(fileobj=BytesIO(resp.content), mode="r:gz")
        temp_dir = mkdtemp()
        tgz.extractall(temp_dir)
        build_dir = os.path.join(temp_dir, os.listdir(temp_dir)[0])

        # Update action.yml image version
        action_path = os.path.join(build_dir, "action.yml")
        with open(action_path) as f:
            action_yml = f.read()
        action_image = yaml.safe_load(action_yml)["runs"]["image"]
        m = re.search("docker://(.*):", action_image)
        if not m:
            fail("Invalid action.yml format (Docker repository could not be parsed)")
        docker_repo = m[1]
        current_version = action_image.split(":")[-1]
        while current_version.count(".") < 2:
            current_version += ".0"
        next_version = getattr(VersionInfo.parse(current_version), f"bump_{bump}")()
        print(f"Next version: v{next_version}")
        action_updated = re.sub(
            r"(image:\s*docker://.*):.*", rf"\1:{next_version}", action_yml
        )

        # Check for existing release
        try:
            gh_repo.get_release(f"v{next_version}")
        except UnknownObjectException:
            pass
        else:
            fail(f"Release v{next_version} already exists")

        # Build and push Docker images
        docker_client = docker.from_env()
        print("Logging into Docker Hub")
        docker_client.login(DOCKER_USERNAME, DOCKER_PASSWORD)
        print("Building image")
        image, build_logs = docker_client.images.build(path=build_dir)
        for build_log in build_logs:
            if "stream" in build_log:
                line = build_log["stream"].strip()
                if line:
                    print(line)
        print("Pushing Docker images")
        docker_tags = [
            f"{next_version.major}.{next_version.minor}.{next_version.patch}",
            f"{next_version.major}.{next_version.minor}",
            f"{next_version.major}",
            "latest",
        ]
        for tag in docker_tags:
            image.tag(docker_repo, tag=tag)
            push_logs = docker_client.images.push(
                docker_repo, tag=tag, stream=True, decode=True
            )
            for push_log in push_logs:
                print(push_log)

        # Update action.yml
        print("Committing action.yml changes")
        message = "Update Docker image version"
        object_hash = sha1(f"blob {len(action_yml)}\0{action_yml}".encode()).hexdigest()
        result = gh_repo.update_file("action.yml", message, action_updated, object_hash)
        commit_sha = result["commit"].sha

        # Update Git tags
        git_tag = f"v{next_version}"
        print("Creating release")
        gh_repo.create_git_release(git_tag, git_tag, changelog)
        git_tags = [
            f"v{next_version.major}",
            f"v{next_version.major}.{next_version.minor}",
            "latest",
        ]
        print("Creating Git tags")
        for tag in git_tags:
            try:
                ref = gh_repo.get_git_ref(f"tags/{tag}")
            except UnknownObjectException:
                pass
            else:
                ref.delete()
            gh_repo.create_git_ref(f"refs/tags/{tag}", commit_sha)

        # React to the issue comment
        issue = gh_repo.get_issue(payload["issue"]["number"])
        comment = issue.get_comment(payload["comment"]["id"])
        comment.create_reaction("+1")
    except Exception:
        # Comment on the isssue
        print("::error ::Docker Action Releaser encountered an unexpected error")
        traceback.print_exc()
        url = f"{gh_repo.html_url}/actions/runs/{RUN_ID}"
        issue = gh_repo.get_issue(payload["issue"]["number"])
        issue.create_comment(f"Something went wrong: {url}")
        sys.exit(1)


if __name__ == "__main__":
    main()
