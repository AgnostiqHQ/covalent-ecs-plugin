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

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "bucket" {
  bucket = "${var.name}-bucket"
  force_destroy = true
}

resource "aws_s3_bucket_acl" "bucket_acl" {
  bucket = aws_s3_bucket.bucket.id
  acl    = "private"
}

resource "aws_ecr_repository" "ecr_repository" {
  name                 = "${var.name}-ecr-repo"
  image_tag_mutability = "IMMUTABLE"

  force_delete = true

  image_scanning_configuration {
    scan_on_push = false
  }
}

resource "aws_cloudwatch_log_group" "log_group" {
  name = "${var.name}-log-group"
}

resource "aws_ecs_cluster" "ecs_cluster" {
  name = "${var.name}-ecs-cluster"

  configuration {
    execute_command_configuration {
      logging    = "OVERRIDE"
      log_configuration {
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.log_group.name
      }
    }
  }
}
