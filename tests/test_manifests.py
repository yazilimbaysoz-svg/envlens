"""Tests for Compose, GitHub Actions and Dockerfile parsers."""

from __future__ import annotations

from envlens.config import Config
from envlens.manifests import parse_dockerfile, parse_yaml_env, scan_manifests


def test_parse_compose_environment_list_and_mapping(tmp_path, write):
    path = write(
        tmp_path,
        "docker-compose.yml",
        """
services:
  api:
    image: api:latest
    environment:
      - DATABASE_URL=postgres://db/api
      - PASS_THROUGH
      - "QUOTED=hello"
      # - COMMENTED=ignored
      NODE_ENV: production
  worker:
    environment: {WORKER_KEY: worker-value, OTHER: 2}
""",
    )
    declarations = parse_yaml_env(path, Config.load(tmp_path))

    by_name = {item.name: item.value for item in declarations}
    assert by_name == {
        "DATABASE_URL": "postgres://db/api",
        "PASS_THROUGH": "",
        "QUOTED": "hello",
        "NODE_ENV": "production",
        "WORKER_KEY": "worker-value",
        "OTHER": "2",
    }


def test_parse_actions_env_blocks(tmp_path, write):
    path = write(
        tmp_path,
        ".github/workflows/ci.yml",
        """
name: CI
env:
  GLOBAL_FLAG: "true"
jobs:
  test:
    env:
      TEST_TIMEOUT: "30"
    steps:
      - run: echo ok
""",
    )
    declarations = parse_yaml_env(path, Config.load(tmp_path))
    assert {item.name: item.value for item in declarations} == {
        "GLOBAL_FLAG": "true",
        "TEST_TIMEOUT": "30",
    }


def test_parse_yaml_handles_empty_sections(tmp_path, write):
    path = write(
        tmp_path, "compose.yml", "services:\n  api:\n    environment:\n    image: api:latest\n"
    )
    assert parse_yaml_env(path, Config.load(tmp_path)) == []


def test_parse_dockerfile_both_forms(tmp_path, write):
    path = write(
        tmp_path,
        "Dockerfile",
        """
FROM python:3.12-slim
ENV APP_ENV=production LOG_LEVEL=info
ENV LEGACY_MODE release
ENV API_KEY="abc123def456"
ENV CONTINUED=one \\
    TWO=two
""",
    )
    declarations = parse_dockerfile(path, Config.load(tmp_path))

    values = {item.name: item.value for item in declarations}
    assert values == {
        "APP_ENV": "production",
        "LOG_LEVEL": "info",
        "LEGACY_MODE": "release",
        "API_KEY": "abc123def456",
        "CONTINUED": "one",
        "TWO": "two",
    }


def test_scan_manifests_filters_relevant_files(tmp_path, write):
    write(tmp_path, "compose.yaml", "environment:\n  FROM_COMPOSE: yes\n")
    write(tmp_path, ".github/workflows/deploy.yml", "env:\n  FROM_ACTIONS: yes\n")
    write(tmp_path, "unrelated.yml", "environment:\n  IGNORED: yes\n")
    write(tmp_path, "Containerfile", "ENV FROM_CONTAINERFILE=1\n")

    declarations = scan_manifests(tmp_path, Config.load(tmp_path))
    names = {item.name for item in declarations}
    assert names == {"FROM_COMPOSE", "FROM_ACTIONS", "FROM_CONTAINERFILE"}
