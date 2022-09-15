# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the GNU Affero General Public License 3.0 (the "License").
# A copy of the License may be obtained with this software package or at
#
#      https://www.gnu.org/licenses/agpl-3.0.en.html
#
# Use of this file is prohibited except in compliance with the License. Any
# modifications or derivative works of this file must retain this copyright
# notice, and modified files must contain a notice indicating that they have
# been altered from the originals.
#
# Covalent is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the License for more details.
#
# Relief from the License may be granted by purchasing a commercial license.

"""AWS ECSExecutor plugin for the Covalent dispatcher."""

import asyncio
import base64
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import boto3
import cloudpickle as pickle
from covalent._shared_files.config import get_config
from covalent._shared_files.logger import app_log
from covalent._shared_files.util_classes import DispatchInfo
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor
from covalent_aws_plugins import AWSExecutor

from .scripts import DOCKER_SCRIPT, PYTHON_EXEC_SCRIPT

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ["HOME"], ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "default",
    "s3_bucket_name": "covalent-fargate-task-resources",
    "ecr_repo_name": "covalent-fargate-task-images",
    "ecs_cluster_name": "covalent-fargate-cluster",
    "ecs_task_family_name": "covalent-fargate-tasks",
    "ecs_task_execution_role_name": "ecsTaskExecutionRole",
    "ecs_task_role_name": "CovalentFargateTaskRole",
    "ecs_task_subnet_id": "",
    "ecs_task_security_group_id": "",
    "ecs_task_log_group_name": "covalent-fargate-task-logs",
    "vcpu": 0.25,
    "memory": 0.5,
    "cache_dir": "/tmp/covalent",
    "poll_freq": 10,
}

EXECUTOR_PLUGIN_NAME = "ECSExecutor"

FUNC_FILENAME = "func-{dispatch_id}-{node_id}.pkl"
RESULT_FILENAME = "result-{dispatch_id}-{node_id}.pkl"
CONTAINER_NAME = "covalent-task-{dispatch_id}-{node_id}"
COVALENT_EXEC_BASE_URI = "public.ecr.aws/covalent/covalent-executor-base:latest"


class ECSExecutor(AWSExecutor):
    """AWS ECSExecutor plugin class.

    Args:
        credentials: Full path to AWS credentials file.
        profile: Name of an AWS profile whose credentials are used.
        s3_bucket_name: Name of an S3 bucket where objects are stored.
        ecr_repo_name: Name of the ECR repository where task images are stored.
        ecs_cluster_name: Name of the ECS cluster on which tasks run.
        ecs_task_family_name: Name of the ECS task family for a user, project, or experiment.
        ecs_task_execution_role_name: Name of the IAM role used by the ECS agent.
        ecs_task_role_name: Name of the IAM role used within the container.
        ecs_task_subnet_id: Valid subnet ID.
        ecs_task_security_group_id: Valid security group ID.
        ecs_task_log_group_name: Name of the CloudWatch log group where container logs are stored.
        vcpu: Number of vCPUs available to a task.
        memory: Memory (in GB) available to a task.
        poll_freq: Frequency with which to poll a submitted task.
        cache_dir: Cache directory used by this executor for temporary files.
    """

    def __init__(
        self,
        credentials: str = None,
        profile: str = None,
        s3_bucket_name: str = None,
        ecr_repo_name: str = None,
        ecs_cluster_name: str = None,
        ecs_task_family_name: str = None,
        ecs_task_execution_role_name: str = None,
        ecs_task_role_name: str = None,
        ecs_task_subnet_id: str = None,
        ecs_task_security_group_id: str = None,
        ecs_task_log_group_name: str = None,
        vcpu: float = None,
        memory: float = None,
        poll_freq: int = None,
        **kwargs,
    ):

        super().__init__(
            credentials_file=credentials,
            profile=profile,
            s3_bucket_name=s3_bucket_name,
            execution_role=ecs_task_execution_role_name,
            poll_freq=poll_freq,
            log_group_name=ecs_task_log_group_name,
            **kwargs,
        )

        self.ecr_repo_name = ecr_repo_name
        self.ecs_cluster_name = ecs_cluster_name
        self.ecs_task_family_name = ecs_task_family_name

        self.ecs_task_role_name = ecs_task_role_name
        self.ecs_task_subnet_id = ecs_task_subnet_id
        self.ecs_task_security_group_id = ecs_task_security_group_id
        self.vcpu = vcpu
        self.memory = memory
        self._cwd = tempfile.mkdtemp()

        if self.cache_dir == "":
            self.cache_dir = get_config("executors.ecs.cache_dir")

        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        if not self._is_valid_subnet_id(self.ecs_task_subnet_id):
            app_log.error(
                f"{self.ecs_task_subnet_id} is not a valid subnet id. Please set a valid subnet id either in the ECS executor definition or in the Covalent config file."
            )

        if not self._is_valid_security_group(self.ecs_task_security_group_id):
            app_log.error(
                f"{self.ecs_task_security_group_id} is not a valid security group id. Please set a valid security group id either in the ECS executor definition or in the Covalent config file."
            )

        config = {
            "profile": self.profile,
            "region": self.region,
            "credentials": self.credentials_file,
            "ecr_repo_name": self.ecr_repo_name,
            "ecs_cluster_name": self.ecs_cluster_name,
            "ecs_task_family_name": self.ecs_task_family_name,
            "ecs_task_role_name": self.ecs_task_role_name,
            "ecs_task_subnet_id": self.ecs_task_subnet_id,
            "ecs_task_security_group_id": self.ecs_task_security_group_id,
            "log_group_name": self.log_group_name,
            "execution_role": self.execution_role,
            "poll_freq": self.poll_freq,
            "vcpu": self.vcpu,
            "memory": self.memory,
            "cache_dir": self.cache_dir,
            "_cwd": self._cwd,
        }
        self._debug_log("Starting ECS Executor with config:")
        app_log.debug(config)

    async def _upload_task(self, function, args, kwargs, task_metadata) -> None:

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]

        s3 = boto3.Session(**self.boto_session_options()).client("s3")
        s3_object_filename = FUNC_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)

        with tempfile.NamedTemporaryFile(dir=self.cache_dir) as function_file:
            # Write serialized function to file
            pickle.dump((function, args, kwargs), function_file)
            function_file.flush()
            s3.upload_file(function_file.name, self.s3_bucket_name, s3_object_filename)

    async def submit_task(self, task_metadata: Dict, identity: Dict) -> None:

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        container_name = CONTAINER_NAME.format(dispatch_id=dispatch_id, node_id=node_id)
        account = identity["Account"]

        dispatch_info = DispatchInfo(dispatch_id)
        with self.get_dispatch_context(dispatch_info):

            ecs = boto3.Session(**self.boto_session_options()).client("ecs")

            # Register the task definition
            self._debug_log("Registering ECS task definition...")
            ecs.register_task_definition(
                family=self.ecs_task_family_name,
                taskRoleArn=self.ecs_task_role_name,
                executionRoleArn=f"arn:aws:iam::{account}:role/{self.execution_role}",
                networkMode="awsvpc",
                requiresCompatibilities=["FARGATE"],
                containerDefinitions=[
                    {
                        "name": container_name,
                        "image": COVALENT_EXEC_BASE_URI,
                        "essential": True,
                        "logConfiguration": {
                            "logDriver": "awslogs",
                            "options": {
                                "awslogs-region": self.region,
                                "awslogs-group": self.log_group_name,
                                "awslogs-create-group": "true",
                                "awslogs-stream-prefix": "covalent-fargate",
                            },
                        },
                        "environment": [
                            {"name": "S3_BUCKET_NAME", "value": self.s3_bucket_name},
                            {
                                "name": "COVALENT_TASK_FUNC_FILENAME",
                                "value": FUNC_FILENAME.format(
                                    dispatch_id=dispatch_id, node_id=node_id
                                ),
                            },
                            {
                                "name": "RESULT_FILENAME",
                                "value": RESULT_FILENAME.format(
                                    dispatch_id=dispatch_id, node_id=node_id
                                ),
                            },
                        ],
                    },
                ],
                cpu=str(int(self.vcpu * 1024)),
                memory=str(int(self.memory * 1024)),
            )

            # Run the task
            response = ecs.run_task(
                taskDefinition=self.ecs_task_family_name,
                launchType="FARGATE",
                cluster=self.ecs_cluster_name,
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": [self.ecs_task_subnet_id],
                        "securityGroups": [self.ecs_task_security_group_id],
                        # This is only needed if we're using public subnets
                        "assignPublicIp": "ENABLED",
                    },
                },
            )
            # Return this task ARN in an async setting
            task_arn = response["tasks"][0]["taskArn"]
            return task_arn

    def _is_valid_subnet_id(self, subnet_id: str) -> bool:
        """Check if the subnet is valid."""

        return re.fullmatch(r"subnet-[0-9a-z]{8,17}", subnet_id) is not None

    def _is_valid_security_group(self, security_group: str) -> bool:
        """Check if the security group is valid."""

        return re.fullmatch(r"sg-[0-9a-z]{8,17}", security_group) is not None

    def _debug_log(self, message):
        app_log.debug(f"AWS ECS Executor: {message}")

    async def run(self, function: Callable, args: List, kwargs: Dict, task_metadata: Dict):

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]

        self._debug_log(f"Executing Dispatch ID {dispatch_id} Node {node_id}")

        self._debug_log("Validating Credentials...")
        identity = self._validate_credentials(raise_exception=True)

        self._debug_log("Uploading task to S3...")
        await self._upload_task(function, args, kwargs, task_metadata)

        self._debug_log("Submitting task...")
        task_arn = await self.submit_task(task_metadata, identity)

        self._debug_log(f"Successfully submitted task with ARN: {task_arn}")

        await self._poll_task(task_arn)

        return await self.query_result(task_metadata)

    async def get_status(self, task_arn: str) -> Tuple[str, int]:
        """Query the status of a previously submitted ECS task.

        Args:
            task_arn: ARN used to identify an ECS task.

        Returns:
            status: String describing the task status.
            exit_code: Exit code, if the task has completed, else -1.
        """
        ecs = boto3.Session(**self.boto_session_options()).client("ecs")
        paginator = ecs.get_paginator("list_tasks")
        page_iterator = paginator.paginate(
            cluster=self.ecs_cluster_name,
            family=self.ecs_task_family_name,
            desiredStatus="STOPPED",
        )

        for page in page_iterator:
            if len(page["taskArns"]) == 0:
                break

            tasks = ecs.describe_tasks(
                cluster=self.ecs_cluster_name,
                tasks=page["taskArns"],
            )["tasks"]

            for task in tasks:
                if task["taskArn"] == task_arn:
                    status = task["lastStatus"]

                    try:
                        exit_code = int(task["containers"][0]["exitCode"])
                    except KeyError:
                        exit_code = -1

                    return status, exit_code

        return ("TASK_NOT_FOUND", -1)

    async def _poll_task(self, task_arn: str) -> None:
        """Poll an ECS task until completion.

        Args:
            task_arn: ARN used to identify an ECS task.

        Returns:
            None
        """
        status, exit_code = await self.get_status(task_arn)

        while status != "STOPPED":
            await asyncio.sleep(self.poll_freq)
            status, exit_code = await self.get_status(task_arn)

        if exit_code != 0:
            raise Exception(f"Task failed with exit code {exit_code}.")

    async def _get_log_events(self, task_arn, task_metadata: Dict):
        """Retrieve log events from from log stream."""
        logs = boto3.Session(**self.boto_session_options()).client("logs")

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        task_id = task_arn.split("/")[-1]

        events = logs.get_log_events(
            logGroupName=self.log_group_name,
            logStreamName=f"covalent-fargate/covalent-task-{dispatch_id}-{node_id}/{task_id}",
        )["events"]

        return "".join(event["message"] + "\n" for event in events)

    async def query_result(self, task_metadata: Dict) -> Tuple[Any, str, str]:
        """Query and retrieve a completed task's result.

        Args:
            task_metadata: Dictionary containing the task dispatch_id and node_id
            task_arn: AWS Identifier for the ECS task

        Returns:
            result: The task's result, as a Python object.
        """

        s3 = boto3.Session(**self.boto_session_options()).client("s3")

        dispatch_id = task_metadata["dispatch_id"]
        node_id = task_metadata["node_id"]
        result_filename = RESULT_FILENAME.format(dispatch_id=dispatch_id, node_id=node_id)
        local_result_filename = os.path.join(self._cwd, result_filename)

        self._debug_log(
            f"Downloading {result_filename} from bucket {self.s3_bucket_name} to local path ${local_result_filename}"
        )
        s3.download_file(self.s3_bucket_name, result_filename, local_result_filename)
        with open(local_result_filename, "rb") as f:
            result = pickle.load(f)
        os.remove(local_result_filename)
        return result

    async def cancel(self, task_arn: str, reason: str = "None") -> None:
        """Cancel an ECS task.

        Args:
            task_arn: ARN used to identify an ECS task.
            reason: An optional string used to specify a cancellation reason.

        Returns:
            None
        """

        ecs = boto3.Session(**self.boto_session_options()).client("ecs")
        ecs.stop_task(cluster=self.ecs_cluster_name, task=task_arn, reason=reason)
