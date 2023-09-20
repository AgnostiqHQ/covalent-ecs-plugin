# Copyright 2021 Agnostiq Inc.
#
# This file is part of Covalent.
#
# Licensed under the Apache License 2.0 (the "License"). A copy of the
# License may be obtained with this software package or at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Use of this file is prohibited except in compliance with the License.
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

output "s3_bucket_name" {
  value       = aws_s3_bucket.bucket.id
  description = "Name of S3 bucket used by fargate tasks"
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.ecs_cluster.name
  description = "Name of ECS cluster"
}

output "ecs_task_execution_role_name" {
  value = aws_iam_role.ecs_tasks_execution_role.name
  description = "Name of IAM task execution role used by container service agent"
}

output "ecs_task_role_name" {
  value = aws_iam_role.task_role.name
  description = "Name of IAM task role used by container during runtime"
}

output "ecs_task_subnet_id" {
  value = var.vpc_id == "" ? module.vpc.public_subnets[0] : var.subnet_id
  description = "ID of VPC public subnet"
}

output "ecs_task_security_group_id" {
  value = aws_security_group.sg.id
  description = "ID of security group"
}

output "ecs_task_log_group_name" {
  value = aws_cloudwatch_log_group.log_group.name
  description = "Name of log group associated with ECS cluster"
}
