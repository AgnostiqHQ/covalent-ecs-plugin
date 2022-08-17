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

"""Unit tests for AWS ECS executor."""

from base64 import b64encode
from unittest.mock import MagicMock

import pytest

from covalent_ecs_plugin.ecs import ECSExecutor
from covalent_ecs_plugin.scripts import DOCKER_SCRIPT, PYTHON_EXEC_SCRIPT


@pytest.fixture
def ecs_executor(mocker):
    mocker.patch("covalent_ecs_plugin.ecs.get_config")
    return ECSExecutor(
        credentials="mock",
        profile="mock",
        s3_bucket_name="mock",
        ecr_repo_name="mock",
        ecs_cluster_name="mock",
        ecs_task_family_name="mock",
        ecs_task_execution_role_name="mock",
        ecs_task_role_name="mock",
        ecs_task_subnet_id="mock",
        ecs_task_security_group_id="mock",
        ecs_task_log_group_name="mock",
        vcpu="mock",
        memory="mock",
        poll_freq="mock",
        cache_dir="mock",
    )


def test_executor_init_default_values(mocker):
    """Test that the init values of the executor are set properly."""
    mocker.patch("covalent_ecs_plugin.ecs.get_config", return_value="mock")
    mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor._is_valid_subnet_id", return_value=False)
    mocker.patch(
        "covalent_ecs_plugin.ecs.ECSExecutor._is_valid_security_group", return_value=False
    )
    ecse = ECSExecutor()
    assert ecse.credentials == "mock"
    assert ecse.profile == "mock"
    assert ecse.s3_bucket_name == "mock"
    assert ecse.ecr_repo_name == "mock"
    assert ecse.ecs_cluster_name == "mock"
    assert ecse.ecs_task_family_name == "mock"
    assert ecse.ecs_task_execution_role_name == "mock"
    assert ecse.ecs_task_role_name == "mock"
    assert ecse.ecs_task_subnet_id == "mock"
    assert ecse.ecs_task_security_group_id == "mock"
    assert ecse.ecs_task_log_group_name == "mock"
    assert ecse.vcpu == "mock"
    assert ecse.memory == "mock"
    assert ecse.poll_freq == "mock"
    assert ecse.cache_dir == "mock"


def test_executor_init_validation(mocker):
    """Test that subnet and security group id is validated."""
    mocker.patch("covalent_ecs_plugin.ecs.get_config", return_value="mock")
    mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor._is_valid_subnet_id", return_value=True)
    mocker.patch(
        "covalent_ecs_plugin.ecs.ECSExecutor._is_valid_security_group", return_value=False
    )


def test_is_valid_subnet_id(ecs_executor):
    """Test the valid subnet checking method."""
    assert ecs_executor._is_valid_subnet_id("subnet-871545e1") is True
    assert ecs_executor._is_valid_subnet_id("subnet-871545e") is False
    assert ecs_executor._is_valid_subnet_id("jlkjlkj871545e1") is False


def test_is_valid_security_group(ecs_executor):
    """Test the valid security group checking method."""
    assert ecs_executor._is_valid_security_group("sg-0043541a") is True
    assert ecs_executor._is_valid_security_group("sg-0043541") is False
    assert ecs_executor._is_valid_security_group("80980043541") is False


def test_get_aws_account(ecs_executor, mocker):
    """Test the method to retrieve the aws account."""
    mm = MagicMock()
    mocker.patch("covalent_ecs_plugin.ecs.boto3.Session", return_value=mm)
    ecs_executor._get_aws_account()
    mm.client().get_caller_identity.called_once_with()
    mm.client().get_caller_identity.get.called_once_with("Account")


def test_execute(mocker):
    """Test the execute method."""
    pass


def test_format_exec_script(ecs_executor):
    """Test method that constructs the executable tasks-execution Python script."""
    kwargs = {
        "func_filename": "mock_function_filename",
        "result_filename": "mock_result_filename",
        "docker_working_dir": "mock_docker_working_dir",
    }
    exec_script = ecs_executor._format_exec_script(**kwargs)
    assert exec_script == PYTHON_EXEC_SCRIPT.format(
        s3_bucket_name=ecs_executor.s3_bucket_name, **kwargs
    )


def test_format_dockerfile(ecs_executor):
    """Test method that constructs the dockerfile."""
    docker_script = ecs_executor._format_dockerfile(
        exec_script_filename="root/mock_exec_script_filename",
        docker_working_dir="mock_docker_working_dir",
    )
    assert docker_script == DOCKER_SCRIPT.format(
        func_basename="mock_exec_script_filename", docker_working_dir="mock_docker_working_dir"
    )


def test_upload_file_to_s3(ecs_executor, mocker):
    """Test method to upload file to s3."""
    mm = MagicMock()
    mocker.patch("covalent_ecs_plugin.ecs.boto3.Session", return_value=mm)
    ecs_executor._upload_file_to_s3(
        "mock_s3_bucket_name", "mock_temp_function_filename", "mock_s3_function_filename"
    )
    mm.client().upload_file.assert_called_once_with(
        "mock_temp_function_filename", "mock_s3_bucket_name", "mock_s3_function_filename"
    )


def test_ecr_info(ecs_executor, mocker):
    """Test method to retrieve ecr related info."""
    mm = MagicMock()
    mm.client().get_authorization_token.return_value = {
        "authorizationData": [
            {
                "authorizationToken": b64encode(b"fake_token"),
                "proxyEndpoint": "proxy_endpoint",
            }
        ]
    }
    mocker.patch("covalent_ecs_plugin.ecs.boto3.Session", return_value=mm)
    assert ecs_executor._get_ecr_info("mock_image_tag") == (
        "fake_token",
        "proxy_endpoint",
        "proxy_endpoint/mock:mock_image_tag",
    )
    mm.client().get_authorization_token.assert_called_once_with()


def test_package_and_upload(ecs_executor, mocker):
    """Test the package and upload method."""
    upload_file_to_s3_mock = mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor._upload_file_to_s3")
    format_exec_script_mock = mocker.patch(
        "covalent_ecs_plugin.ecs.ECSExecutor._format_exec_script", return_value=""
    )
    format_dockerfile_mock = mocker.patch(
        "covalent_ecs_plugin.ecs.ECSExecutor._format_dockerfile", return_value=""
    )
    get_ecr_info_mock = mocker.patch(
        "covalent_ecs_plugin.ecs.ECSExecutor._get_ecr_info",
        return_value=("", "", ""),
    )
    mocker.patch("covalent_ecs_plugin.ecs.shutil.copyfile")
    mm = MagicMock()
    tag_mock = MagicMock()
    mm.images.build.return_value = tag_mock, "logs"
    mocker.patch("covalent_ecs_plugin.ecs.docker.from_env", return_value=mm)

    ecs_executor._package_and_upload(
        "mock_transportable_object",
        "mock_image_tag",
        "mock_task_results_dir",
        "mock_result_filename",
        [],
        {},
    )
    upload_file_to_s3_mock.assert_called_once()
    format_exec_script_mock.assert_called_once()
    format_dockerfile_mock.assert_called_once()
    get_ecr_info_mock.assert_called_once()


def test_get_status(mocker, ecs_executor):
    """Test the status checking method."""
    ecs_mock = MagicMock()
    ecs_mock.get_paginator().paginate.return_value = []  # Case 1: no tasks found
    res = ecs_executor.get_status(ecs_mock, "")
    assert res == ("TASK_NOT_FOUND", -1)

    ecs_mock.get_paginator().paginate.return_value = [
        {"taskArns": ["mock_task_arn"]}
    ]  # Case 2 valid task found
    ecs_mock.describe_tasks.return_value = {
        "tasks": [
            {"taskArn": "mock_task_arn", "lastStatus": "RUNNING", "containers": [{"exitCode": 1}]}
        ]
    }
    res = ecs_executor.get_status(ecs_mock, "mock_task_arn")
    assert res == ("RUNNING", 1)

    ecs_mock.get_paginator().paginate.return_value = [
        {"taskArns": ["mock_task_arn"]}
    ]  # Case 3 - task found without any status
    ecs_mock.describe_tasks.return_value = {
        "tasks": [{"taskArn": "mock_task_arn", "lastStatus": "FAILED"}]
    }
    res = ecs_executor.get_status(ecs_mock, "mock_task_arn")
    assert res == ("FAILED", -1)


def test_poll_ecs_task(mocker, ecs_executor):
    """Test the method to poll the ecs task."""


def test_query_result(mocker):
    """Test the method to query the result."""
    pass


def test_cancel(mocker):
    """Test the execution cancellation method."""
    pass
