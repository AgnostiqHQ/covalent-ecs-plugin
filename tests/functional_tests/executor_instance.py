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


import os

import covalent as ct
import terraform_output

ECS_EXECUTOR_S3_BUCKET = terraform_output.get("s3_bucket_name", "covalent-fargate-task-resources")
ECS_EXECUTOR_ECR_REPO = terraform_output.get("ecr_repo_name", "covalent-fargate-task-images")
ECS_EXECUTOR_ECS_CLUSTER = terraform_output.get("ecs_cluster_name", "covalent-fargate-cluster")
ECS_EXECUTOR_TASK_FAMILY_NAME = terraform_output.get(
    "ecs_task_family_name", "covalent-fargate-tasks"
)
ECS_EXECUTOR_EXECUTION_ROLE_NAME = terraform_output.get(
    "ecs_task_execution_role_name", "ecsTaskExecutionRole"
)
ECS_EXECUTOR_TASK_ROLE_NAME = terraform_output.get("ecs_task_role_name", "CovalentFargateTaskRole")
ECS_EXECUTOR_TASK_LOG_GROUP_NAME = terraform_output.get(
    "ecs_task_log_group_name", "covalent-fargate-task-logs"
)
ECS_EXECUTOR_TASK_SUBNET_ID = terraform_output.get("ecs_task_subnet_id", "")
ECS_EXECUTOR_TASK_SECURITY_GROUP_NAME = terraform_output.get("ecs_task_security_group_id", "")

executor_config = {
    "s3_bucket_name": os.getenv("ECS_EXECUTOR_S3_BUCKET", ECS_EXECUTOR_S3_BUCKET),
    "ecr_repo_name": os.getenv("ECS_EXECUTOR_ECR_REPO", ECS_EXECUTOR_ECR_REPO),
    "ecs_cluster_name": os.getenv("ECS_EXECUTOR_ECS_CLUSTER", ECS_EXECUTOR_ECS_CLUSTER),
    "ecs_task_family_name": os.getenv(
        "ECS_EXECUTOR_TASK_FAMILY_NAME", ECS_EXECUTOR_TASK_FAMILY_NAME
    ),
    "ecs_task_execution_role_name": os.getenv(
        "ECS_EXECUTOR_EXECUTION_ROLE_NAME", ECS_EXECUTOR_EXECUTION_ROLE_NAME
    ),
    "ecs_task_role_name": os.getenv("ECS_EXECUTOR_TASK_ROLE_NAME", ECS_EXECUTOR_TASK_ROLE_NAME),
    "ecs_task_log_group_name": os.getenv(
        "ECS_EXECUTOR_TASK_LOG_GROUP_NAME", ECS_EXECUTOR_TASK_LOG_GROUP_NAME
    ),
    "ecs_task_subnet_id": os.getenv("ECS_EXECUTOR_TASK_SUBNET_ID", ECS_EXECUTOR_TASK_SUBNET_ID),
    "ecs_task_security_group_id": os.getenv(
        "ECS_EXECUTOR_TASK_SECURITY_GROUP_NAME", ECS_EXECUTOR_TASK_SECURITY_GROUP_NAME
    ),
    "vcpu": os.getenv("ECS_EXECUTOR_VCPU", 0.25),
    "memory": os.getenv("ECS_EXECUTOR_MEMORY", 0.5),
    "cache_dir": "/tmp/covalent",
}

print("Using Executor Config:")
print(executor_config)

executor = ct.executor.ECSExecutor(**executor_config)
