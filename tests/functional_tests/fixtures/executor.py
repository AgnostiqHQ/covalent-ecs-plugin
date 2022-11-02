from dotenv import load_dotenv

load_dotenv()

import os

from covalent_ecs_plugin.ecs import ECSExecutor

executor_config = {
    "s3_bucket_name": os.getenv("executor_s3_bucket_name"),
    "ecr_repo_name": os.getenv("executor_ecr_repo_name"),
    "ecs_cluster_name": os.getenv("executor_ecs_cluster_name"),
    "ecs_task_family_name": os.getenv("executor_ecs_task_family_name"),
    "ecs_task_execution_role_name": os.getenv("executor_ecs_task_execution_role_name"),
    "ecs_task_role_name": os.getenv("executor_ecs_task_role_name"),
    "ecs_task_log_group_name": os.getenv("executor_ecs_task_log_group_name"),
    "ecs_task_subnet_id": os.getenv("executor_ecs_task_subnet_id"),
    "ecs_task_security_group_id": os.getenv("executor_ecs_task_security_group_id"),
    "vcpu": os.getenv("executor_vcpu", 0.25),
    "memory": os.getenv("executor_memory", 0.5),
    "cache_dir": "/tmp/covalent",
}

print("Using Executor Configuration:")
print(executor_config)

executor = ECSExecutor(**executor_config)
