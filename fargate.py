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

import base64
import os
import shutil
import subprocess

import boto3
import docker

from typing import Any, Dict, List, Tuple

from covalent._shared_files.util_classes import DispatchInfo
from covalent._workflow.transport import TransportableObject
from covalent.executor import BaseExecutor

# TODO: Create defaults dict

executor_plugin_name = "FargateExecutor"

class FargateExecutor(BaseExecutor):
    """AWS Fargate executor plugin class.

    Args:
        None
    """

    def __init__(
        self,
        credentials = "", #filename
        profile: Optional[str] = None, #credential profile
        s3_uri = "",
        ecr_repo_name = "covalent-fargate",
        ecs_cluster,
        ecs_service
    ):
        super().__init__()

        self.credentials = credentials
        self.profile = profile
        self.s3_uri = s3_uri
        self.ecr_repo_name = ecr_repo_name

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

        os.environ["AWS_SHARED_CREDENTIALS_FILE"] = self.credentials

        with self.get_dispatch_context(dispatch_info), tempfile.NamedTemporaryFile(dir=self.cache_dir) as f, tempfile.NamedTemporaryFile(dir=self.cache_dir) as g:

            # Write execution script to file
            python_script = """
import os
import boto3
import cloudpickle as pickle

local_func_filename = os.path.join({docker_working_dir}, {func_filename})
local_result_filename = os.path.join({docker_working_dir}, {result_filename})

s3 = boto3.client("s3")
s3.download_file({s3_uri}, {func_filename}, local_func_filename)

with open(local_func_filename, "rb") as f:
    function = pickle.load(f).get_deserialized()

result = function(*{args}, **{kwargs})

with open(local_result_filename, "wb") as f:
    pickle.dump(result, f)

s3.upload_file(local_result_filename, {s3_uri}, {result_filename})
""".format(
                func_filename=func_filename,
                args=args,
                kwargs=kwargs,
                s3_uri=self.s3_uri,
                result_filename=result_filename,
                docker_working_dir=docker_working_dir,
            )
            f.write(python_script)
            f.flush()

            # Write Dockerfile
            dockerfile = """
FROM python:3.8-slim-buster

RUN apt-get update && apt-get install -y \
  gcc \
  && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --use-feature=in-tree-build boto3 cloudpickle

COPY {func_filename} {docker_working_dir}

WORKDIR {docker_working_dir}

ENTRYPOINT [ "python" ]
CMD ["{docker_working_dir}/{func_filename}"]
""".format(
                func_filename=f.name,
                docker_working_dir=docker_working_dir,
            )
            g.write(dockerfile)
            g.flush()

            local_dockerfile = os.path.join(task_results_dir, f"Dockerfile-{dispatch_id}-{node_id}")
            shutil.copyfile(g.name, local_dockerfile)

            image_tag = f"{dispatch_id}-{node_id}"

            # Build the Docker image
            docker_client = docker.from_env()
            image, build_log = docker_client.images.build(
                dockerfile=local_dockerfile, 
                tag=image_tag
            )

            # ECR Login
            ecr = boto3.client("ecr", profile_name=self.profile)

            ecr_username = "AWS"
            ecr_credentials = ecr.get_authorization_token()["authorizationData"][0]
            ecr_password = base64.b64decode(ecr_credentials["authorizationToken"]).replace(b"AWS:", b"").decode("utf-8")
            ecr_url = ecr_credentials["proxyEndpoint"]
            ecr_repo_uri = f"{ecr_url.replace('https://', '')}/{self.ecr_repo_name}:{image_tag}"

            docker_client.login(username=ecr_username, password=ecr_password, registry=ecr_url)

            # Tag the image
            image.tag(ecr_repo_uri, tag=image_tag)

            # Push to ECR
            result = docker_client.images.push(ecr_repo_uri, tag=image_tag)

            # Deploy on ECS
            ecs = boto3.client("ecs", profile_name=self.profile)
            ecs.update_service(
                cluster=self.ecs_cluster, 
                service=self.ecs_service, 
                forceNewDeployment=True
            )

            return 42
