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

"""AWS Fargate executor plugin for the Covalent dispatcher."""

# Infrastructure required for this executor:
#       1. VPC
#          - IPv4 CIDR: 10.0.0.0/16
#       2. Private Subnets (1 per zone)
#          - IPv4 CIDR: 10.0.X.0/24
#       3. Route Table
#       4. Elastic IP
#       5. NAT Gateway
#       6. Outbound route to NAT Gateway
#          - 0.0.0.0/0 -> NAT Addr
#       7. Security Group (empty)
#       8. S3 Bucket
#       9. ECR Repository
#          - Immutable tags
#          - KMS encryption
#       10. ECS Cluster
#       11. CloudWatch Log Group
#       12. IAM Policy - CovalentFargateTaskExecutionPolicy (see below)
#       13. IAM Role - CovalentFargateTaskExecutionRole
#       14. IAM Policy - CovalentFargateTaskPolicy (see below)
#       15. IAM Role - CovalentFargateTaskRole
#       16. IAM Policy - CovalentFargateExecutorPolicy (see below)
#       17. IAM Policy - CovalentFargateExecutorInfraPolicy (see below)
#       18. ECS Task Definition - created at runtime
#       19. ECS Task - created at runtime


# IAM policies needed for the actions related to this executor:
#       1. CovalentFargateExecutorPolicy: the policy needed to use the FargateExecutor, without
#          provisioning infrastructure; below is an in-progress list.
#          - Action:
#            - s3:GetObject
#            - s3:PutObject
#            - s3:ListBucket
#            Resource:
#            - arn:aws:s3:::covalent-fargate-task-resources/*
#            - arn:aws:s3:::covalent-fargate-task-resources
#          - Action:
#            - ecr:PutImage
#            - ecr:UploadLayerPart
#            - ecr:InitiateLayerUpload
#            - ecr:CompleteLayerUpload
#            Resource:
#            - arn:aws:ecr:::repository/covalent-fargate-task-images
#          - Action:
#            - ecr:GetAuthorizationToken
#            Resource: *
#          - Action:
#            - ecs:RegisterTaskDefinition
#            - ecs:RunTask
#            - ecs:ListTasks
#            - ecs:DescribeTasks
#            Resource:
#            - arn:aws:ecs:::container-instance/covalent-fargate-cluster/*
#          - Action:
#            - logs:GetLogEvents
#            Resource:
#            - arn:aws:logs:::log-group:covalent-fargate-task-logs:log-stream:*
#       2. CovalentFargateExecutorInfraPolicy: Same as above, except additionally allowing provisioning;
#          Below is an in-progress list.
#          - Action:
#            - logs:CreateLogGroup
#            - ecs:CreateCluster
#            - ecr:CreateRepository
#            - s3:CreateBucket
#            Resource: *
#       3. CovalentFargateTaskExecutionPolicy: ECS task execution role's policy (complete list)
#          - Action:
#            - ecr:GetAuthorizationToken
#            - ecr:BatchCheckLayerAvailability
#            - ecr:GetDownloadUrlForLayer
#            - ecr:BatchGetImage
#            - logs:CreateLogStream
#            - logs:PutLogEvents
#            Resource: *
#       4. CovalentFargateTaskPolicy: ECS task's policy (used to grant permissions to the script running
#          within the Docker container). Below is a complete list.
#          - Action:
#            - s3:PutObject
#            - s3:GetObject
#            - s3:ListBucket
#            Resource:
#            - arn:aws:s3:::covalent-fargate-task-resources/*
#            - arn:aws:s3:::covalent-fargate-task-resources
#          - Action:
#            - braket:*
#            Resource: *


# Network configuration:
#       1. There are new changes in Fargate 1.4.0 which require the ECS agent to be able to communicate
#          to the internet in order to access ECR images. This means that either we use public subnets
#          in a VPC connected to an internet gateway, or we can use private subnets which route
#          0.0.0.0/0 to one or more NAT gateways. If we choose the former option, it is important to
#          provide "assignPublicIp": "ENABLED" in the network configuration when calling ecs.run_task.
#       2. For the purposes of testing this executor, the default VPC and default subnets are used in
#          us-east-1. These fall into the first category above.
#       3. The recommended option for production is to use a set of private subnets all connected
#          to the same NAT gateway. This also will need a dedicated VPC.


# Synchronization:
#       1. Consider adding a sync/async bool option to execute.  Sync should poll the result, while
#          async should include a callback within the script that's run on the remote machine. This will
#          allow the runner to interact with any given executor in both ways; we expect synchronous behavior
#          in a self-hosted runner, and async behavior in the hosted (Covalent Cloud) runner.
#       2. The lifecycle of an ECS task includes [Provisioning -> Pending -> Activating -> Running ->
#          Deactivating -> Stopping -> Deprovisioning -> Stopped]. Polling means waiting until the Stopped
#          state has been reached, then returning the


import base64
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import boto3
import cloudpickle as pickle
import docker
from covalent._shared_files.logger import app_log
from covalent._shared_files.util_classes import DispatchInfo
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE")
    or os.path.join(os.environ["HOME"], ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "",
    "s3_bucket_name": "covalent-fargate-task-resources",
    "ecr_repo_name": "covalent-fargate-task-images",
    "ecs_cluster_name": "covalent-fargate-cluster",
    "ecs_task_family_name": "covalent-fargate-tasks",
    "ecs_task_execution_role_name": "ecsTaskExecutionRole",
    "ecs_task_role_name": "CovalentFargateTaskRole",
    "ecs_task_vpc": "",
    "ecs_task_subnets": "",
    "ecs_task_security_groups": "",
    "ecs_task_log_group_name": "covalent-fargate-task-logs",
    "vcpu": 0.25,
    "memory": 0.5,
    "cache_dir": "/tmp/covalent",
    "poll_freq": 30,
}

executor_plugin_name = "FargateExecutor"


class FargateExecutor(BaseExecutor):
    """AWS Fargate executor plugin class.

    Args:
        credentials: Full path to AWS credentials file.
        profile: Name of an AWS profile whose credentials are used.
        s3_bucket_name: Name of an S3 bucket where objects are stored.
        ecr_repo_name: Name of the ECR repository where task images are stored.
        ecs_cluster_name: Name of the ECS cluster on which tasks run.
        ecs_task_family_name: Name of the ECS task family for a user, project, or experiment.
        ecs_task_execution_role_name: Name of the IAM role used by the ECS agent.
        ecs_task_role_name: Name of the IAM role used within the container.
        ecs_task_vpc: VPC where tasks run.
        ecs_task_subnets: List of subnets where tasks run, as a comma-separated string.
        ecs_task_security_groups: List of security groups attached to tasks, as a comma-separated string.
        ecs_task_log_group_name: Name of the CloudWatch log group where container logs are stored.
        vcpu: Number of vCPUs available to a task.
        memory: Memory (in GB) available to a task.
        poll_freq: Frequency with which to poll a submitted task.
        cache_dir: Cache directory used by this executor for temporary files.
    """

    def __init__(
        self,
        credentials: str,
        profile: str,
        s3_bucket_name: str,
        ecr_repo_name: str,
        ecs_cluster_name: str,
        ecs_task_family_name: str,
        ecs_task_execution_role_name: str,
        ecs_task_role_name: str,
        ecs_task_vpc: str,
        ecs_task_subnets: str,
        ecs_task_security_groups: str,
        ecs_task_log_group_name: str,
        vcpu: float,
        memory: float,
        poll_freq: int,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.credentials = credentials
        self.profile = profile
        self.s3_bucket_name = s3_bucket_name
        self.ecr_repo_name = ecr_repo_name
        self.ecs_cluster_name = ecs_cluster_name
        self.ecs_task_family_name = ecs_task_family_name
        self.ecs_task_execution_role_name = ecs_task_execution_role_name
        self.ecs_task_role_name = ecs_task_role_name
        self.ecs_task_vpc = ecs_task_vpc
        self.ecs_task_subnets = ecs_task_subnets
        self.ecs_task_security_groups = ecs_task_security_groups
        self.ecs_task_log_group_name = ecs_task_log_group_name
        self.vcpu = vcpu
        self.memory = memory
        self.poll_freq = poll_freq

    def execute(
        self,
        function: TransportableObject,
        args: List,
        kwargs: Dict,
        dispatch_id: str,
        results_dir: str,
        node_id: int = -1,
    ) -> Tuple[Any, str, str]:

        dispatch_info = DispatchInfo(dispatch_id)
        result_filename = f"result-{dispatch_id}-{node_id}.pkl"
        task_results_dir = os.path.join(results_dir, dispatch_id)
        image_tag = f"{dispatch_id}-{node_id}"
        container_name = f"covalent-task-{image_tag}"

        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = self.credentials
        os.environ["AWS_PROFILE"] = self.profile

        # TODO: Move this to BaseExecutor
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        with self.get_dispatch_context(dispatch_info):
            ecr_repo_uri = self._package_and_upload(
                function,
                image_tag,
                task_results_dir,
                result_filename,
                args,
                kwargs,
            )

            # ECS config
            ecs = boto3.client("ecs")

            # Register the task definition
            account = boto3.client("sts").get_caller_identity()["Account"]
            ecs.register_task_definition(
                family=self.ecs_task_family_name,
                taskRoleArn=self.ecs_task_role_name,
                executionRoleArn=f"arn:aws:iam::{account}:role/{self.ecs_task_execution_role_name}",
                networkMode="awsvpc",
                requiresCompatibilities=["FARGATE"],
                containerDefinitions=[
                    {
                        "name": container_name,
                        "image": ecr_repo_uri,
                        "essential": True,
                        "logConfiguration": {
                            "logDriver": "awslogs",
                            "options": {
                                "awslogs-region": "us-east-1",
                                "awslogs-group": self.ecs_task_log_group_name,
                                "awslogs-create-group": "true",
                                "awslogs-stream-prefix": "covalent-fargate",
                            },
                        },
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
                        "subnets": self.ecs_task_subnets.split(","),
                        "securityGroups": self.ecs_task_security_groups.split(","),
                        # This is only needed if we're using public subnets
                        "assignPublicIp": "ENABLED",
                    },
                },
            )

            # Return this task ARN in an async setting
            task_arn = response["tasks"][0]["taskArn"]

            self._poll_ecs_task(ecs, task_arn)

            return self._query_result(result_filename, task_results_dir, task_arn, image_tag)

    def _format_exec_script(
        self,
        func_filename: str,
        result_filename: str,
        docker_working_dir: str,
        args: List,
        kwargs: Dict,
    ) -> str:
        """Create an executable Python script which executes the task.

        Args:
            func_filename: Name of the pickled function.
            result_filename: Name of the pickled result.
            docker_working_dir: Name of the working directory in the container.
            args: Positional arguments consumed by the task.
            kwargs: Keyword arguments consumed by the task.

        Returns:
            script: String object containing the executable Python script.
        """

        exec_script = """
import os
import boto3
import cloudpickle as pickle

local_func_filename = os.path.join("{docker_working_dir}", "{func_filename}")
local_result_filename = os.path.join("{docker_working_dir}", "{result_filename}")

s3 = boto3.client("s3")
s3.download_file("{s3_bucket_name}", "{func_filename}", local_func_filename)

with open(local_func_filename, "rb") as f:
    function = pickle.load(f)

result = function(*{args}, **{kwargs})

with open(local_result_filename, "wb") as f:
    pickle.dump(result, f)

s3.upload_file(local_result_filename, "{s3_bucket_name}", "{result_filename}")
""".format(
            func_filename=func_filename,
            args=args,
            kwargs=kwargs,
            s3_bucket_name=self.s3_bucket_name,
            result_filename=result_filename,
            docker_working_dir=docker_working_dir,
        )

        return exec_script

    def _format_dockerfile(self, exec_script_filename: str, docker_working_dir: str) -> str:
        """Create a Dockerfile which wraps an executable Python task.
        
        Args:
            exec_script_filename: Name of the executable Python script.
            docker_working_dir: Name of the working directory in the container.

        Returns:
            dockerfile: String object containing a Dockerfile.
        """

        dockerfile = """
FROM python:3.8-slim-buster

RUN apt-get update && apt-get install -y \\
  gcc \\
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --use-feature=in-tree-build boto3 cloudpickle

WORKDIR {docker_working_dir}

COPY {func_filename} {docker_working_dir}

ENTRYPOINT [ "python" ]
CMD ["{docker_working_dir}/{func_basename}"]
""".format(
            func_filename=exec_script_filename,
            func_basename=os.path.basename(exec_script_filename),
            docker_working_dir=docker_working_dir,
        )

        return dockerfile

    def _package_and_upload(
        self,
        function: TransportableObject,
        image_tag: str,
        task_results_dir: str,
        result_filename: str,
        args: List,
        kwargs: Dict,
    ) -> str:
        """Package a task using Docker and upload it to AWS ECR.
        
        Args:
            function: A callable Python function.
            image_tag: Tag used to identify the Docker image.
            task_results_dir: Local directory where task results are stored.
            result_filename: Name of the pickled result.
            args: Positional arguments consumed by the task.
            kwargs: Keyword arguments consumed by the task.

        Returns:
            ecr_repo_uri: URI of the repository where the image was uploaded.
        """

        func_filename = f"func-{image_tag}.pkl"
        docker_working_dir = "/opt/covalent"

        with tempfile.NamedTemporaryFile(dir=self.cache_dir) as function_file:
            # Write serialized function to file
            pickle.dump(function.get_deserialized(), function_file)
            function_file.flush()

            # Upload pickled function to S3
            s3 = boto3.client("s3")
            s3.upload_file(function_file.name, self.s3_bucket_name, func_filename)

        with tempfile.NamedTemporaryFile(
            dir=self.cache_dir, mode="w"
        ) as exec_script_file, tempfile.NamedTemporaryFile(
            dir=self.cache_dir, mode="w"
        ) as dockerfile_file:
            # Write execution script to file
            exec_script = self._format_exec_script(
                func_filename,
                result_filename,
                docker_working_dir,
                args,
                kwargs,
            )
            exec_script_file.write(exec_script)
            exec_script_file.flush()

            # Write Dockerfile to file
            dockerfile = self._format_dockerfile(exec_script_file.name, docker_working_dir)
            dockerfile_file.write(dockerfile)
            dockerfile_file.flush()

            local_dockerfile = os.path.join(task_results_dir, f"Dockerfile_{image_tag}")
            shutil.copyfile(dockerfile_file.name, local_dockerfile)

            # Build the Docker image
            docker_client = docker.from_env()
            image, build_log = docker_client.images.build(
                path=self.cache_dir, dockerfile=dockerfile_file.name, tag=image_tag
            )

        # ECR config
        ecr = boto3.client("ecr")

        ecr_username = "AWS"
        ecr_credentials = ecr.get_authorization_token()["authorizationData"][0]
        ecr_password = (
            base64.b64decode(ecr_credentials["authorizationToken"])
            .replace(b"AWS:", b"")
            .decode("utf-8")
        )
        ecr_registry = ecr_credentials["proxyEndpoint"]
        ecr_repo_uri = f"{ecr_registry.replace('https://', '')}/{self.ecr_repo_name}:{image_tag}"

        docker_client.login(username=ecr_username, password=ecr_password, registry=ecr_registry)

        # Tag the image
        image.tag(ecr_repo_uri, tag=image_tag)

        # Push to ECR
        docker_client.images.push(ecr_repo_uri, tag=image_tag)

        return ecr_repo_uri

    def get_status(self, ecs, task_arn: str) -> Tuple[str, int]:
        """Query the status of a previously submitted ECS task.

        Args:
            ecs: ECS client object.
            task_arn: ARN used to identify an ECS task.

        Returns:
            status: String describing the task status.
            exit_code: Exit code, if the task has completed, else -1.
        """

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

    def _poll_ecs_task(self, ecs, task_arn: str) -> None:
        """Poll an ECS task until completion.

        Args:
            ecs: ECS client object.
            task_arn: ARN used to identify an ECS task.

        Returns:
            None
        """

        status, exit_code = self.get_status(ecs, task_arn)

        while status != "STOPPED":
            time.sleep(self.poll_freq)
            status, exit_code = self.get_status(ecs, task_arn)

        if exit_code != 0:
            raise Exception(f"Task failed with exit code {exit_code}.")

    def _query_result(
        self,
        result_filename: str,
        task_results_dir: str,
        task_arn: str,
        image_tag: str,
    ) -> Tuple[Any, str, str]:
        """Query and retrieve a completed task's result.

        Args:
            result_filename: Name of the pickled result file.
            task_results_dir: Local directory where task results are stored.
            task_arn: ARN used to identify an ECS task.
            image_tag: Tag used to identify the Docker image.

        Returns:
            result: The task's result, as a Python object.
            logs: The stdout and stderr streams corresponding to the task.
            empty_string: A placeholder empty string.
        """

        local_result_filename = os.path.join(task_results_dir, result_filename)

        s3 = boto3.client("s3")
        s3.download_file(self.s3_bucket_name, result_filename, local_result_filename)

        with open(local_result_filename, "rb") as f:
            result = pickle.load(f)
        os.remove(local_result_filename)

        task_id = task_arn.split("/")[-1]
        logs = boto3.client("logs")

        # TODO: This should be paginated, but the command doesn't support boto3 pagination
        # Up to 10000 log events can be returned from a single call to get_log_events()
        events = logs.get_log_events(
            logGroupName=self.ecs_task_log_group_name,
            logStreamName=f"covalent-fargate/covalent-task-{image_tag}/{task_id}",
        )["events"]

        log_events = ""
        for event in events:
            log_events += event["message"] + "\n"

        return result, log_events, ""

    def cancel(self, task_arn: str, reason: str = "None") -> None:
        """Cancel an ECS task.

        Args:
            task_arn: ARN used to identify an ECS task.
            reason: An optional string used to specify a cancellation reason.

        Returns:
            None
        """

        ecs = boto3.client("ecs")
        ecs.stop_task(cluster=self.ecs_cluster_name, task=task_arn, reason=reason)
