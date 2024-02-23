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

variable "prefix" {
  default     = ""
  description = "Name used to prefix AWS resources"
}

variable "region" {
  default     = "us-east-1"
  description = "Region in which Covalent is deployed"
}

variable "vpc_id" {
  default     = ""
  description = "Existing VPC ID"
}

variable "subnet_id" {
  default     = ""
  description = "Existing subnet ID"
}

variable "vpc_cidr" {
  default     = "10.0.0.0/24"
  description = "VPC CIDR range"
}

variable "cache_dir" {
  type        = string
  default     = "/tmp/covalent"
  description = "Path on local machine where temporary files are generated"
}

variable "poll_freq" {
  type        = number
  default     = 5
  description = "Frequency with which to poll AWS batch for the result object"
}

variable "vcpus" {
  type        = number
  default     = 2
  description = "Number of vcpus a batch job will consume by default"
}

variable "memory" {
  type        = number
  default     = 2
  description = "Memory in GB for the batch job"
}

variable "credentials" {
  type        = string
  default     = ""
  description = "Path to the AWS shared configuration file"
}

variable "profile" {
  type        = string
  description = "AWS profile used during execution"
}
