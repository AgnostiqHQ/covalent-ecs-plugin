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

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "bucket" {
  bucket = "${var.prefix}-bucket"
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "ownership_controls" {
  bucket = aws_s3_bucket.bucket.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "bucket_acl" {
  depends_on = [aws_s3_bucket_ownership_controls.ownership_controls]
  bucket     = aws_s3_bucket.bucket.id
  acl        = "private"
}

resource "aws_ecr_repository" "ecr_repository" {
  name                 = "${var.prefix}-ecr-repo"
  image_tag_mutability = "IMMUTABLE"

  force_delete = true

  image_scanning_configuration {
    scan_on_push = false
  }
}

resource "aws_cloudwatch_log_group" "log_group" {
  name = "${var.prefix}-log-group"
}

resource "aws_ecs_cluster" "ecs_cluster" {
  name = "${var.prefix}-ecs-cluster"

  configuration {
    execute_command_configuration {
      logging    = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.log_group.name
      }
    }
  }
}

# Executor Covalent config section
data template_file executor_config {
  template = "${file("${path.module}/ecs.conf.tftpl")}"

  vars = {
    credentials=var.credentials
    profile=var.profile
    region=var.aws_region
    s3_bucket_name=aws_s3_bucket.bucket.id
    ecs_cluster_name=aws_ecs_cluster.ecs_cluster.name
    ecs_task_execution_role_name=aws_iam_role.ecs_tasks_execution_role.name
    ecs_task_role_name=aws_iam_role.task_role.name
    ecs_task_subnet_id=module.vpc.public_subnets[0]
    ecs_task_security_group_id=aws_security_group.sg.id
    ecs_task_log_group_name=aws_cloudwatch_log_group.log_group.name
    vcpu=var.vcpus
    memory=var.memory
    cache_dir=var.cache_dir
    poll_freq=var.poll_freq
  }
}

resource local_file executor_config {
  content = data.template_file.executor_config.rendered
  filename = "${path.module}/ecs.conf"
}
