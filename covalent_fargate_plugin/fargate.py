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

# TODO: There are several IAM policies to consider:
#       1. The policy needed to use the FargateExecutor, without provisioning infrastructure
#       2. Same as above, except additionally allowing provisioning
#       3. ECS task execution role's policy
#       4. ECS task's policy (used to grant permissions to the script running within the Docker container)

# TODO: Consider adding a sync/async bool option to execute.  Sync should poll the result, while
#       async should include a callback within the script that's run on the remote machine. This will
#       allow the runner to interact with any given executor in both ways; we expect synchronous behavior
#       in a self-hosted runner, and async behavior in the hosted (Covalent Cloud) runner.

import base64
import os
import shutil
import subprocess
import tempfile

import boto3
import docker

import cloudpickle as pickle

from pathlib import Path
from typing import Any, Dict, List, Tuple

from covalent._shared_files.util_classes import DispatchInfo
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor

from covalent._shared_files.logger import app_log

_EXECUTOR_PLUGIN_DEFAULTS = {
    "credentials": os.environ.get("AWS_SHARED_CREDENTIALS_FILE") or os.path.join(os.environ["HOME"], ".aws/credentials"),
    "profile": os.environ.get("AWS_PROFILE") or "",
    "s3_bucket_name": "covalent-fargate-task-resources",
    "ecr_repo_name": "covalent-fargate-task-images",
    "ecs_cluster_name": "covalent-fargate-cluster",
    "ecs_task_family_name": "covalent-fargate-tasks",
    "ecs_task_role_name": "CovalentFargateTaskRole",
    "vcpu": 0.25,
    "memory": 0.5,
    "provision": False,
    "cache_dir": "/tmp/covalent"
}

executor_plugin_name = "FargateExecutor"

class FargateExecutor(BaseExecutor):
    """AWS Fargate executor plugin class.

    Args:
        None
    """

    def __init__(
        self,
        credentials: str,
        profile: str,
        s3_bucket_name: str,
        ecr_repo_name: str,
        ecs_cluster_name: str,
        ecs_task_family_name: str,
        ecs_task_role_name: str,
        vcpu: float,
        memory: float,
        provision: bool,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.credentials = credentials
        self.profile = profile
        self.s3_bucket_name = s3_bucket_name
        self.ecr_repo_name = ecr_repo_name
        self.ecs_cluster_name = ecs_cluster_name
        self.ecs_task_family_name = ecs_task_family_name
        self.ecs_task_role_name = ecs_task_role_name
        self.vcpu = vcpu
        self.memory = memory
        self.provision = provision

    def execute(
        self,
        function: TransportableObject,
        args: List,
        kwargs: Dict,
        dispatch_id: str,
        results_dir: str,
        node_id: int = -1,
    ) -> Tuple[Any, str, str]:
        
        print("Inside Fargate!")
        dispatch_info = DispatchInfo(dispatch_id)
        func_filename = f"func-{dispatch_id}-{node_id}.pkl"
        result_filename = f"result-{dispatch_id}-{node_id}.pkl"
        task_results_dir = os.path.join(results_dir, dispatch_id)
        docker_working_dir = "/opt/covalent"
        image_tag = f"{dispatch_id}-{node_id}"

        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = self.credentials
        os.environ["AWS_PROFILE"] = self.profile

        # TODO: Move this to BaseExecutor
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

        if self.provision:
            app_log.warning("The FargateExecutor's 'provision' flag is intended for debugging purposes only, and enabling it is *not* efficient. For general usage, use the accompanying CDK script to provision and manage persistent cloud resources.")

        with self.get_dispatch_context(dispatch_info), \
            tempfile.NamedTemporaryFile(dir=self.cache_dir) as function_file, \
            tempfile.NamedTemporaryFile(dir=self.cache_dir, mode="w") as script_file, \
            tempfile.NamedTemporaryFile(dir=self.cache_dir, mode="w") as dockerfile_file:

            # Write serialized function to file
            pickle.dump(function, function_file)
            function_file.flush()

            # Upload pickled function to S3
            s3 = boto3.client("s3")
            s3.upload_file(function_file.name, self.s3_bucket_name, func_filename)

            # Write execution script to file
            python_script = """
import os
import boto3
import cloudpickle as pickle

local_func_filename = os.path.join("{docker_working_dir}", "{func_filename}")
local_result_filename = os.path.join("{docker_working_dir}", "{result_filename}")

s3 = boto3.client("s3")
s3.download_file("{s3_bucket_name}", "{func_filename}", local_func_filename)

with open(local_func_filename, "rb") as f:
    function = pickle.load(f).get_deserialized()

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
            script_file.write(python_script)
            script_file.flush()

            # Write Dockerfile
            dockerfile = """
FROM python:3.8-slim-buster

RUN apt-get update && apt-get install -y \\
  gcc \\
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --use-feature=in-tree-build boto3 cloudpickle

WORKDIR {docker_working_dir}

COPY {func_basename} {docker_working_dir}

ENTRYPOINT [ "python" ]
CMD ["{docker_working_dir}/{func_basename}"]
""".format(
                func_filename=script_file.name,
                func_basename=os.path.basename(script_file.name),
                docker_working_dir=docker_working_dir,
            )
            dockerfile_file.write(dockerfile)
            dockerfile_file.flush()

            local_dockerfile = os.path.join(task_results_dir, f"Dockerfile_node-{node_id}")
            shutil.copyfile(dockerfile_file.name, local_dockerfile)

            # Build the Docker image
            docker_client = docker.from_env()
            image, build_log = docker_client.images.build(
                path=self.cache_dir,
                dockerfile=dockerfile_file.name, 
                tag=image_tag
            )
            return f"{image_tag}", "", ""
            # TODO: Continue testing here

            # ECR config
            ecr = boto3.client("ecr")

            ecr_username = "AWS"
            ecr_credentials = ecr.get_authorization_token()["authorizationData"][0]
            ecr_password = base64.b64decode(ecr_credentials["authorizationToken"]).replace(b"AWS:", b"").decode("utf-8")
            ecr_registry = ecr_credentials["proxyEndpoint"]
            ecr_repo_uri = f"{ecr_registry.replace('https://', '')}/{self.ecr_repo_name}:{image_tag}"
            account = ecr_repo_uri.split(".")[0]

            docker_client.login(username=ecr_username, password=ecr_password, registry=ecr_registry)

            if self.provision:
                # Check if the repo already exists
                repo_exists = False
                # TODO: Handle paginated response using get_paginator
                response = ecr.describe_repositories(registryId=ecr_registry)
                repos = response["repositories"]
                for repo in repos:
                    if repo["repositoryName"] == self.ecr_repo_name:
                        repo_exists = True
                        break

                # Create the ECR repo
                if not repo_exists:
                    ecr.create_repository(
                        registryId=ecr_registry,
                        repositoryName=self.ecr_repo_name,
                        imageTagMutability="IMMUTABLE",
                        encryptionConfiguration={
                            "encryptionType": "KMS",
                        },
                    )
                    # TODO: Check response

            # Tag the image
            image.tag(ecr_repo_uri, tag=image_tag)

            # Push to ECR
            result = docker_client.images.push(ecr_repo_uri, tag=image_tag)

            # ECS config
            ecs = boto3.client("ecs", profile_name=self.profile)

            if self.provision:
                # Check if the cluster already exists
                cluster_exists = False
                paginator = ecs.get_paginator("list_clusters")
                page_iterator = paginator.paginate()
                for page in page_iterator:
                    if cluster_exists:
                        break

                    for arn in page["clusterArns"]:
                        cluster_name = ecs.describe_clusters(clusters=[arn])["clusters"][0]["clusterName"]
                        if cluster_name == self.ecs_cluster_name:
                            cluster_exists = True
                            break

                #Create the ECS cluster
                if not cluster_exists:
                    ecs.create_cluster(clusterName=self.ecs_cluster_name)
                    #TODO: Check response

                # Check if the task role already exists
                # TODO: Need to check the role as well as the corresponding policy
                #       The policy will need to allow access to S3 and Braket
                ecs_task_role_exists = False
                iam = boto3.client("iam", profile_name=self.profile)
                roles = iam.list_roles()["Roles"]
                for role in roles:
                    if roles["RoleName"] == self.ecs_task_role_name:
                        ecs_task_role_exists = True
                        break

                # Create the role used by the container
                iam.create_role(
                    RoleName=self.ecs_task_role_name,
                    #TODO: continue filling this in
                )


                # Check if task definition family already exists
                task_family_exists = False
                paginator = ecs.get_paginator("list_task_definition_families")
                page_iterator = paginator.paginate()
                for page in page_iterator:
                    if page["families"] == self.ecs_task_family_name:
                        task_family_exists = True
                        break

                # Create the task definition
                if not task_family_exists:
                    ecs.register_task_definition(
                        family=self.ecs_task_family_name,
                        taskRoleArn=self.ecs_task_role_name,
                        executionRoleArn=f"arn:aws:iam::{account}:role/ecsTaskExecutionRole",
                        networkMode="awsvpc",
                        requiresCompabilities=["FARGATE"],
                        containerDefinitions=[
                            {
                                "name": f"covalent-task-{image_tag}",
                                "image": ecr_repo_uri,
                                "essential": True,
                            },
                        ],
                        cpu=str(self.cpu*1024),
                        memory=str(self.memory*1024),
                    )
                    #TODO: Check response

            # Run the task
            response = ecs.run_task(
                taskDefinition=self.ecs_task_family_name,
                launchType="FARGATE",
                cluster=self.ecs_cluster_name,
                count=1,
                networkConfiguration={
                    "awsvpcConfiguration": {
                        "subnets": [], #TODO: Provision a subnet
                    },
                },
            )
            # TODO: Check response

            # TODO: Either poll and return a result (sync) or return response status (async)

            return 42
