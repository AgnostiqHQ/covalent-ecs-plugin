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

import os
from pathlib import Path
from unittest import mock
from unittest.mock import AsyncMock

import cloudpickle as pickle
import pytest

from covalent_ecs_plugin.ecs import FUNC_FILENAME, RESULT_FILENAME, ECSExecutor


class TestECSExecutor:

    MOCK_PROFILE = "my_profile"
    MOCK_S3_BUCKET_NAME = "s3-bucket"
    MOCK_ECS_CLUSTER_NAME = "ecs-cluster"
    MOCK_ECS_TASK_FAMILY_NAME = "task-family-name"
    MOCK_ECS_EXECUTION_ROLE = "task-execution-role"
    MOCK_ECS_TASK_ROLE_NAME = "task-role-name"
    MOCK_ECS_TASK_SUBNET_ID = "sb-1234"
    MOCK_ECS_TASK_SG_ID = "sg-123"
    MOCK_ECS_LOG_GROUP_NAME = "log-group"
    MOCK_VCPU = 0.1234
    MOCK_MEMORY = "123"
    MOCK_POLL_FREQ = 123
    MOCK_DISPATCH_ID = 112233
    MOCK_NODE_ID = 1
    MOCK_TASK_ARN = "task-arn/123"

    @property
    def MOCK_FUNC_FILENAME(self):
        return FUNC_FILENAME.format(dispatch_id=self.MOCK_DISPATCH_ID, node_id=self.MOCK_NODE_ID)

    @property
    def MOCK_RESULT_FILENAME(self):
        return RESULT_FILENAME.format(dispatch_id=self.MOCK_DISPATCH_ID, node_id=self.MOCK_NODE_ID)

    @property
    def MOCK_TASK_METADATA(self):
        return {"dispatch_id": self.MOCK_DISPATCH_ID, "node_id": self.MOCK_NODE_ID}

    @pytest.fixture
    def mock_executor_config(self, tmp_path):
        MOCK_CREDENTIALS_FILE: Path = tmp_path / "credentials"
        MOCK_CREDENTIALS_FILE.touch()
        return {
            "profile": self.MOCK_PROFILE,
            "s3_bucket_name": self.MOCK_S3_BUCKET_NAME,
            "ecs_cluster_name": self.MOCK_ECS_CLUSTER_NAME,
            "ecs_task_family_name": self.MOCK_ECS_TASK_FAMILY_NAME,
            "ecs_task_execution_role_name": self.MOCK_ECS_EXECUTION_ROLE,
            "ecs_task_role_name": self.MOCK_ECS_TASK_ROLE_NAME,
            "ecs_task_subnet_id": self.MOCK_ECS_TASK_SUBNET_ID,
            "ecs_task_security_group_id": self.MOCK_ECS_TASK_SG_ID,
            "ecs_task_log_group_name": self.MOCK_ECS_LOG_GROUP_NAME,
            "vcpu": self.MOCK_VCPU,
            "memory": self.MOCK_MEMORY,
            "poll_freq": self.MOCK_POLL_FREQ,
        }

    @pytest.fixture
    def mock_executor(self, mock_executor_config):
        # mocker.patch("tempfile")
        return ECSExecutor(**mock_executor_config)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_init_explicit_values(self, mocker, mock_executor_config):
        """Test executor class values are overridden properly during instantiation"""

        # only call to get_config is get_config("executors.ecs.cache_dir")
        mocker.patch("covalent_ecs_plugin.ecs.get_config", return_value="mock_cache_dir")
        mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor._is_valid_subnet_id", return_value=True)
        mocker.patch(
            "covalent_ecs_plugin.ecs.ECSExecutor._is_valid_security_group", return_value=True
        )

        executor = ECSExecutor(**mock_executor_config)

        assert executor.profile == self.MOCK_PROFILE
        assert executor.s3_bucket_name == self.MOCK_S3_BUCKET_NAME
        assert executor.ecs_task_family_name == self.MOCK_ECS_TASK_FAMILY_NAME
        assert executor.execution_role == self.MOCK_ECS_EXECUTION_ROLE
        assert executor.ecs_task_role_name == self.MOCK_ECS_TASK_ROLE_NAME
        assert executor.ecs_task_subnet_id == self.MOCK_ECS_TASK_SUBNET_ID
        assert executor.ecs_task_security_group_id == self.MOCK_ECS_TASK_SG_ID
        assert executor.log_group_name == self.MOCK_ECS_LOG_GROUP_NAME
        assert executor.vcpu == self.MOCK_VCPU
        assert executor.memory == self.MOCK_MEMORY
        assert executor.poll_freq == self.MOCK_POLL_FREQ

    @pytest.mark.asyncio
    async def test_upload_file_to_s3(self, mock_executor, mocker):
        """Test to upload file to s3."""
        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")

        def some_function():
            pass

        await mock_executor._upload_task_to_s3(
            some_function,
            self.MOCK_DISPATCH_ID,
            self.MOCK_NODE_ID,
            ("some_arg"),
            {"some": "kwarg"},
        )
        boto3_mock.Session().client().upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_task(self, mock_executor, mocker):
        """Test for method to call the upload task method."""

        def some_function(x):
            return x

        upload_to_s3_mock = mocker.patch(
            "covalent_ecs_plugin.ecs.ECSExecutor._upload_task_to_s3", return_value=AsyncMock()
        )

        await mock_executor._upload_task(some_function, (1), {}, self.MOCK_TASK_METADATA)
        upload_to_s3_mock.assert_called_once_with(
            self.MOCK_DISPATCH_ID, self.MOCK_NODE_ID, some_function, (1), {}
        )

    @pytest.mark.asyncio
    async def test_submit_task(self, mock_executor, mocker):
        """Test submit task method."""
        MOCK_IDENTITY = {"Account": 1234}
        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")
        await mock_executor.submit_task(self.MOCK_TASK_METADATA, MOCK_IDENTITY)
        boto3_mock.Session().client().register_task_definition.assert_called_once()
        boto3_mock.Session().client().run_task.assert_called_once()

    def test_is_valid_subnet_id(self, mock_executor):
        """Test the valid subnet checking method."""
        assert mock_executor._is_valid_subnet_id("subnet-871545e1") is True
        assert mock_executor._is_valid_subnet_id("subnet-871545e") is False
        assert mock_executor._is_valid_subnet_id("jlkjlkj871545e1") is False

    def test_is_valid_security_group(self, mock_executor):
        """Test the valid security group checking method."""
        assert mock_executor._is_valid_security_group("sg-0043541a") is True
        assert mock_executor._is_valid_security_group("sg-0043541") is False
        assert mock_executor._is_valid_security_group("80980043541") is False

    @pytest.mark.asyncio
    async def test_cancel(self, mocker, mock_executor):
        """Test the execution cancellation method."""
        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")
        await mock_executor.cancel("mock_task_arn", "mock_reason")
        boto3_mock.Session().client().stop_task.assert_called_once_with(
            cluster=self.MOCK_ECS_CLUSTER_NAME, task="mock_task_arn", reason="mock_reason"
        )

    @pytest.mark.asyncio
    async def test_query_result(self, mocker, mock_executor, tmp_path: Path):
        """Test the method to query the result."""

        mock_cwd = tmp_path
        mock_executor._cwd = mock_cwd.resolve()
        mock_local_result_path = mock_cwd / self.MOCK_RESULT_FILENAME
        mock_local_result_path.touch()

        MOCK_RESULT_CONTENTS = "mock_result"

        with open(mock_local_result_path, "wb") as f:
            pickle.dump(MOCK_RESULT_CONTENTS, f)

        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")
        result = await mock_executor.query_result(task_metadata=self.MOCK_TASK_METADATA)
        assert result == MOCK_RESULT_CONTENTS

        boto3_mock.Session().client().download_file.assert_called_once_with(
            self.MOCK_S3_BUCKET_NAME, self.MOCK_RESULT_FILENAME, str(mock_local_result_path)
        )

    @pytest.mark.asyncio
    async def test_get_log_events(self, mocker, mock_executor):
        """Test the method to retrieve the log events from the log stream."""

        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")
        boto3_mock.Session().client().get_log_events.return_value = {
            "events": [{"message": "hello"}, {"message": "world"}]
        }
        log_events = await mock_executor._get_log_events(
            "task-arn", task_metadata=self.MOCK_TASK_METADATA
        )
        assert log_events == "hello\nworld\n"

    @pytest.mark.asyncio
    async def test_get_status(self, mocker, mock_executor):
        """Test the status checking method."""
        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")
        ecs_client_mock = boto3_mock.Session().client()

        # Case 1: no tasks found
        ecs_client_mock.get_paginator().paginate.return_value = []
        res = await mock_executor.get_status(self.MOCK_TASK_ARN)
        assert res == ("TASK_NOT_FOUND", -1)

        # Case 2 valid task found
        ecs_client_mock.get_paginator().paginate.return_value = [
            {"taskArns": [self.MOCK_TASK_ARN]}
        ]
        ecs_client_mock.describe_tasks.return_value = {
            "tasks": [
                {
                    "taskArn": self.MOCK_TASK_ARN,
                    "lastStatus": "RUNNING",
                    "containers": [{"exitCode": 1}],
                }
            ]
        }
        res = await mock_executor.get_status(self.MOCK_TASK_ARN)
        assert res == ("RUNNING", 1)

        # Case 3 - task found without any status
        ecs_client_mock.get_paginator().paginate.return_value = [
            {"taskArns": [self.MOCK_TASK_ARN]}
        ]
        ecs_client_mock.describe_tasks.return_value = {
            "tasks": [{"taskArn": self.MOCK_TASK_ARN, "lastStatus": "FAILED"}]
        }
        res = await mock_executor.get_status(self.MOCK_TASK_ARN)
        assert res == ("FAILED", -1)

    @pytest.mark.asyncio
    async def test_poll_ecs_task(self, mocker, mock_executor):
        """Test the method to poll the ecs task."""

        mock_executor.poll_freq = self.MOCK_POLL_FREQ
        sleep_mock = mocker.patch("covalent_ecs_plugin.ecs.asyncio.sleep")

        mocker.patch(
            "covalent_ecs_plugin.ecs.ECSExecutor.get_status",
            side_effect=[("RUNNING", 1), ("STOPPED", 0)],
        )
        await mock_executor._poll_task(self.MOCK_TASK_ARN)
        sleep_mock.assert_called_once_with(self.MOCK_POLL_FREQ)

        with pytest.raises(Exception):
            await mock_executor._poll_task(self.MOCK_TASK_ARN)

    @pytest.mark.asyncio
    async def test_run(self, mocker, mock_executor):
        """Test the run method."""

        MOCK_IDENTITY = {"Account": 1234}
        mock_executor.vcpu = 1
        mock_executor.memory = 1

        def mock_func(x):
            return x

        boto3_mock = mocker.patch("covalent_ecs_plugin.ecs.boto3")

        upload_task_mock = mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor._upload_task")
        validate_credentials_mock = mocker.patch(
            "covalent_ecs_plugin.ecs.ECSExecutor._validate_credentials"
        )
        submit_task_mock = mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor.submit_task")
        _poll_task_mock = mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor._poll_task")
        query_result_mock = mocker.patch("covalent_ecs_plugin.ecs.ECSExecutor.query_result")

        validate_credentials_mock.return_value = MOCK_IDENTITY

        await mock_executor.run(
            function=mock_func, args=[], kwargs={"x": 1}, task_metadata=self.MOCK_TASK_METADATA
        )

        upload_task_mock.assert_called_once_with(mock_func, [], {"x": 1}, self.MOCK_TASK_METADATA)
        validate_credentials_mock.assert_called_once()
        submit_task_mock.assert_called_once_with(self.MOCK_TASK_METADATA, MOCK_IDENTITY)

        returned_task_arn = await submit_task_mock()

        _poll_task_mock.assert_called_once_with(returned_task_arn)
        query_result_mock.assert_called_once_with(self.MOCK_TASK_METADATA)
