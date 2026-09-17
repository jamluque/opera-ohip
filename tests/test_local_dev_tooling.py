from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

import yaml


def test_docker_compose_allows_postgres_port_override() -> None:
    config = yaml.safe_load(Path("docker-compose.yml").read_text(encoding="utf-8"))

    assert "${POSTGRES_PORT:-5432}:5432" in config["services"]["postgres"]["ports"]


def test_init_local_aws_passes_redrive_policy_as_json(tmp_path: Path) -> None:
    calls = tmp_path / "aws-calls.jsonl"
    aws = tmp_path / "aws"
    aws.write_text(
        textwrap.dedent(
            f"""\
            #!/usr/bin/env python3
            import json
            import sys

            calls = {str(calls)!r}
            args = sys.argv[1:]
            with open(calls, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(args) + "\\n")

            if "get-queue-attributes" in args:
                print("arn:aws:sqs:eu-west-1:000000000000:opera-ohip-dev-events-dlq.fifo")
            elif "create-queue" in args:
                name = args[args.index("--queue-name") + 1]
                print(json.dumps({{"QueueUrl": "http://localhost:4566/000000000000/" + name}}))
            """
        ),
        encoding="utf-8",
    )
    aws.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "eu-west-1",
        "ENDPOINT_URL": "http://localhost:4566",
    }

    subprocess.run(["bash", "scripts/init-local-aws.sh"], check=True, env=env)

    create_queue_calls = [
        json.loads(line)
        for line in calls.read_text(encoding="utf-8").splitlines()
        if "create-queue" in json.loads(line)
    ]
    queue_call = next(
        call for call in create_queue_calls if "opera-ohip-dev-events.fifo" in call
    )
    attributes = json.loads(queue_call[queue_call.index("--attributes") + 1])
    redrive_policy = attributes["RedrivePolicy"]

    assert json.loads(redrive_policy) == {
        "deadLetterTargetArn": "arn:aws:sqs:eu-west-1:000000000000:opera-ohip-dev-events-dlq.fifo",
        "maxReceiveCount": "5",
    }
