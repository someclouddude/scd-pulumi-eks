import pulumi
from eks_cluster import cluster, node_group
from alb_controller import tag_subnets_for_eks_and_alb
import pulumi_aws as aws

config = pulumi.Config()
vpc_id = config.require('vpc_id')
public_subnet_ids = config.require_object('public_subnet_ids')
private_subnet_ids = config.require_object('private_subnet_ids')

tag_subnets_for_eks_and_alb(vpc_id, public_subnet_ids, private_subnet_ids)

pulumi.export('cluster_name', cluster.name)
pulumi.export('node_group_name', node_group.node_group_name)
