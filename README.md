&nbsp;

<div align="center">

![covalent logo](https://github.com/AgnostiqHQ/covalent/blob/master/doc/source/_static/dark.png#gh-dark-mode-only)
![covalent logo](https://github.com/AgnostiqHQ/covalent/blob/master/doc/source/_static/light.png#gh-light-mode-only)

&nbsp;

</div>

## Covalent Fargate Plugin

Covalent is a Pythonic workflow tool used to execute tasks on advanced computing hardware. This executor plugin interfaces Covalent with AWS Fargate via the [Elastic Container Service](https://docs.aws.amazon.com/ecs/index.html). In order for workflows to be deployable, users must have AWS credentials attached to the [CovalentFargateExecutorPolicy](https://github.com/AgnostiqHQ/covalent-fargate-executor/infra/iam/CovalentFargateExecutorPolicy.json). Users will need additional permissions to provision or manage cloud infrastructure used by this plugin.

To use this plugin with Covalent, clone this repository and install it using `pip`:

```
git clone git@github.com:AgnostiqHQ/covalent-fargate-plugin.git
cd covalent-fargate-plugin
pip install .
```

Users must add the correct entries to their Covalent [configuration](https://covalent.readthedocs.io/en/latest/how_to/config/customization.html) to support the Fargate plugin. Below is an example which works using some basic infrastructure created for testing purposes:

```console
[executors.fargate]
credentials = "/home/user/.aws/credentials"
profile = ""
s3_bucket_name = "covalent-fargate-task-resources"
ecr_repo_name = "covalent-fargate-task-images"
ecs_cluster_name = "covalent-fargate-cluster"
ecs_task_family_name = "covalent-fargate-tasks"
ecs_task_role_name = "CovalentFargateTaskRole"
vcpu = 0.25
memory = 0.5
cache_dir = "/tmp/covalent"
ecs_task_subnets = "subnet-994c4697,subnet-861e43d9,subnet-779cc356,subnet-326a0e03,subnet-871545e1,subnet-6793732b"
ecs_task_vpc = "vpc-b2bdd0cf"
ecs_task_security_groups = "sg-0043541a"
poll_freq = 10
ecs_task_execution_role_name = "ecsTaskExecutionRole"
ecs_task_log_group_name = "covalent-fargate-task-logs"
```

Within a workflow, users can then decorate electrons using these default settings:

```python
import covalent as ct

@ct.electron(executor="fargate")
def my_task(x, y):
    return x + y
```

or use a class object to customize the resources and other behavior:

```python
executor = ct.executor.FargateExecutor(
    vcpu=1,
    memory=2
)

@ct.electron(executor=executor)
def my_custom_task(x, y):
    return x + y
```

For more information about how to get started with Covalent, check out the project [homepage](https://github.com/AgnostiqHQ/covalent) and the official [documentation](https://covalent.readthedocs.io/en/latest/).

## Release Notes

Release notes are available in the [Changelog](https://github.com/AgnostiqHQ/covalent-fargate-executor/blob/main/CHANGELOG.md).

## Citation

Please use the following citation in any publications:

> W. J. Cunningham, S. K. Radha, F. Hasan, J. Kanem, S. W. Neagle, and S. Sanand.
> *Covalent.* Zenodo, 2022. https://doi.org/10.5281/zenodo.5903364

## License

Covalent is licensed under the GNU Affero GPL 3.0 License. Covalent may be distributed under other licenses upon request. See the [LICENSE](https://github.com/AgnostiqHQ/covalent-fargate-executor/blob/main/LICENSE) file or contact the [support team](mailto:support@agnostiq.ai) for more details.
