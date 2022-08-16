&nbsp;

<div align="center">

<img src="https://raw.githubusercontent.com/AgnostiqHQ/covalent-ecs-plugin/main/assets/aws_ecs_readme_banner.jpg" width=150%>

</div>

## Covalent ECS Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with AWS [Elastic Container Service](https://docs.aws.amazon.com/ecs/index.html) where the tasks are run using Fargate. In order for workflows to be deployable, users must have AWS credentials attached to the [CovalentECSExecutorPolicy](https://github.com/AgnostiqHQ/covalent-ecs-plugin/blob/main/infra/iam/CovalentECSExecutorPolicy.json). Users will need additional permissions to provision or manage cloud infrastructure used by this plugin.

To use this plugin with Covalent, clone this repository and install it using `pip`:

```
git clone git@github.com:AgnostiqHQ/covalent-ecs-plugin.git
cd covalent-ecs-plugin
pip install .
```

Users must add the correct entries to their Covalent [configuration](https://covalent.readthedocs.io/en/latest/how_to/config/customization.html) to support the ECS plugin. Below is an example which works using some basic infrastructure created for testing purposes:

```console
[executors.ecs]
credentials = "/home/user/.aws/credentials"
profile = "default"
s3_bucket_name = "covalent-fargate-task-resources"
ecr_repo_name = "covalent-fargate-task-images"
ecs_cluster_name = "covalent-fargate-cluster"
ecs_task_family_name = "covalent-fargate-tasks"
ecs_task_execution_role_name = "ecsTaskExecutionRole"
ecs_task_role_name = "CovalentFargateTaskRole"
ecs_task_subnet_id = "subnet-871545e1"
ecs_task_security_group_id = "sg-0043541a"
ecs_task_log_group_name = "covalent-fargate-task-logs"
vcpu = 0.25
memory = 0.5
cache_dir = "/tmp/covalent"
poll_freq = 10
```

Within a workflow, users can then decorate electrons using these default settings:

```python
import covalent as ct

@ct.electron(executor="ecs")
def my_task(x, y):
    return x + y
```

or use a class object to customize the resources and other behavior:

```python
executor = ct.executor.ECSExecutor(
    vcpu=1,
    memory=2,
    ecs_task_subnet_id="subnet-871545e1",
    ecs_task_security_group_id="sg-0043541a"
)

@ct.electron(executor=executor)
def my_custom_task(x, y):
    return x + y
```

Ensure that Docker is running on the client side machine before deploying the workflow.

For more information about how to get started with Covalent, check out the project [homepage](https://github.com/AgnostiqHQ/covalent) and the official [documentation](https://covalent.readthedocs.io/en/latest/).

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-ecs-executor/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-ecs-executor/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
