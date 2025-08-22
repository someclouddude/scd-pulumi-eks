import pulumi
from eks_cluster import cluster, node_group

pulumi.export('cluster_name', cluster.name)
pulumi.export('node_group_name', node_group.node_group_name)
