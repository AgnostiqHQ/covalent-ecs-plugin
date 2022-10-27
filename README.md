&nbsp;

<div align="center">

<img src="https://raw.githubusercontent.com/AgnostiqHQ/covalent-ecs-plugin/main/assets/aws_ecs_readme_banner.jpg" width=150%>

[![covalent](https://img.shields.io/badge/covalent-0.177.0-purple)](https://github.com/AgnostiqHQ/covalent)
[![python](https://img.shields.io/pypi/pyversions/covalent-ecs-plugin)](https://github.com/AgnostiqHQ/covalent-ecs-plugin)
[![tests](https://github.com/AgnostiqHQ/covalent-ecs-plugin/actions/workflows/tests.yml/badge.svg)](https://github.com/AgnostiqHQ/covalent-ecs-plugin/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/AgnostiqHQ/covalent-ecs-plugin/branch/main/graph/badge.svg?token=QNTR18SR5H)](https://codecov.io/gh/AgnostiqHQ/covalent-ecs-plugin)
[![agpl](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0.en.html)

</div>

## Covalent ECS Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with AWS [Elastic Container Service (ECS)](https://docs.aws.amazon.com/ecs/index.html) where the tasks are run using Fargate.

## 1. Installation

To use this plugin with Covalent, install it using `pip`:

```sh
pip install covalent-ecs-plugin
```

## 2. Usage Example

This is an example of how a workflow can be constructed to use the AWS ECS executor. In the example, we train a Support Vector Machine (SVM) and use an instance of the executor to execute the `train_svm` electron. Note that we also require [DepsPip](https://covalent.readthedocs.io/en/latest/concepts/concepts.html#depspip) which will be required to execute the electrons.

```python
from numpy.random import permutation
from sklearn import svm, datasets
import covalent as ct

deps_pip = ct.DepsPip(
    packages=["numpy==1.22.4", "scikit-learn==1.1.2"]
)

executor = ct.executor.ECSExecutor(
    s3_bucket_name="covalent-fargate-task-resources",
    ecr_repo_name="covalent-fargate-task-images",
    ecs_cluster_name="covalent-fargate-cluster",
    ecs_task_execution_role_name="ecsTaskExecutionRole",
    ecs_task_role_name="CovalentFargateTaskRole",
    ecs_task_subnet_id="subnet-871545e1",
    ecs_task_security_group_id="sg-0043541a",
    ecs_task_log_group_name="covalent-fargate-task-logs",
    vcpu=1,
    memory=2,
    poll_freq=10,
)


# Use executor plugin to train our SVM model
@ct.electron(
    executor=executor,
    deps_pip=deps_pip
)
def train_svm(data, C, gamma):
    X, y = data
    clf = svm.SVC(C=C, gamma=gamma)
    clf.fit(X[90:], y[90:])
    return clf

@ct.electron
def load_data():
    iris = datasets.load_iris()
    perm = permutation(iris.target.size)
    iris.data = iris.data[perm]
    iris.target = iris.target[perm]
    return iris.data, iris.target

@ct.electron
def score_svm(data, clf):
    X_test, y_test = data
    return clf.score(
    	X_test[:90],y_test[:90]
    )

@ct.lattice
def run_experiment(C=1.0, gamma=0.7):
    data = load_data()
    clf = train_svm(
    	data=data,
	    C=C,
	    gamma=gamma
    )
    score = score_svm(
    	data=data,
	    clf=clf
    )
    return score

# Dispatch the workflow.
dispatch_id = ct.dispatch(run_experiment)(
        C=1.0,
        gamma=0.7
)

# Wait for our result and get result value
result = ct.get_result(dispatch_id, wait=True).result

print(result)
```
During the execution of the workflow, one can navigate to the UI to see the status of the workflow. Once completed, the above script should also output a value with the score of our model.

```sh
0.8666666666666667
```

In order for the above workflow to run successfully, one has to provision the required cloud resources as mentioned in the section [Required AWS Resources](#-required-aws-resources).

## 3. Configuration

There are many configuration options that can be passed into the `ct.executor.ECSExecutor` class or by modifying the [covalent config file](https://covalent.readthedocs.io/en/latest/how_to/config/customization.html) under the section `[executors.ecs]`

For more information about all of the possible configuration values, visit our [read the docs (RTD) guide](https://covalent.readthedocs.io/en/latest/api/executors/awsecs.html)
for this plugin.

## 4. Required AWS Resources

In order for workflows to leverage this executor, users must ensure that all the necessary IAM permissions are properly setup and configured. This executor uses the [S3](https://aws.amazon.com/s3/), [ECR](https://aws.amazon.com/ecr/), and [ECS](https://aws.amazon.com/ecs/) services to execute an electron, thus the required IAM roles and policies must be configured correctly. Precisely, the following resources are needed for the executor to run any dispatched electrons properly.

| Resource     | Config Name      | Description |
| ------------ | ---------------- | ----------- |
| IAM Role     | ecs_task_execution_role_name | The IAM role used by the ECS agent |
| IAM Role     | ecs_task_role_name | The IAM role used by the container during runtime |
| S3 Bucket     | s3_bucket_name | The name of the S3 bucket where objects are stored |
| ECR repository     | ecr_repo_name | The name of the ECR repository where task images are stored  |
| ECS Cluster     | ecs_cluster_name   | The name of the ECS cluster on which your tasks are executed  |
| VPC Subnet    | ecs_task_subnet_id   | The ID of the subnet where instances are created |
| Security group     | ecs_task_security_group_id   | The ID of the security group for task instances |
| Cloudwatch log group     | ecs_task_log_group_name   | The name of the CloudWatch log group where container logs are stored |
| CPU     | vCPU   | The number of vCPUs available to a task |
| Memory     | memory   | The memory (in GB) available to a task |

## Getting Started with Covalent

For more information on how to get started with Covalent, check out the project [homepage](https://github.com/AgnostiqHQ/covalent) and the official [documentation](https://covalent.readthedocs.io/en/latest/).

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-ecs-executor/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-ecs-executor/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
