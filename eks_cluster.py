import pulumi
import pulumi_aws as aws

config = pulumi.Config()
cluster_name = config.get('cluster_name') or 'scd-dev-eks'
vpc_id = config.require('vpc_id')
public_subnet_ids = config.require_object('public_subnet_ids')
private_subnet_ids = config.require_object('private_subnet_ids')

# IAM Role for EKS Cluster
cluster_role = aws.iam.Role('eksClusterRole',
    assume_role_policy='''{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "eks.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'''
)
aws.iam.RolePolicyAttachment('eksClusterRole-Attach1',
    role=cluster_role.name,
    policy_arn='arn:aws:iam::aws:policy/AmazonEKSClusterPolicy'
)
aws.iam.RolePolicyAttachment('eksClusterRole-Attach2',
    role=cluster_role.name,
    policy_arn='arn:aws:iam::aws:policy/AmazonEKSServicePolicy'
)

# IAM Role for Node Group
node_group_role = aws.iam.Role('eksNodeGroupRole',
    assume_role_policy='''{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }'''
)
aws.iam.RolePolicyAttachment('eksNodeGroupRole-Attach1',
    role=node_group_role.name,
    policy_arn='arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy'
)
aws.iam.RolePolicyAttachment('eksNodeGroupRole-Attach2',
    role=node_group_role.name,
    policy_arn='arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly'
)
aws.iam.RolePolicyAttachment('eksNodeGroupRole-Attach3',
    role=node_group_role.name,
    policy_arn='arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy'
)

# EKS Cluster
cluster = aws.eks.Cluster('eksCluster',
    role_arn=cluster_role.arn,
    vpc_config={
        "public_access_cidrs": ["0.0.0.0/0"],
        "endpoint_public_access": True,
        "endpoint_private_access": True,
        "subnet_ids": public_subnet_ids + private_subnet_ids,
    },
    version="1.31",
    name=cluster_name
)

# Managed Node Group
node_group = aws.eks.NodeGroup('eksNodeGroup',
    cluster_name=cluster.name,
    node_role_arn=node_group_role.arn,
    subnet_ids=private_subnet_ids,
    scaling_config={
        "desired_size": 2,
        "min_size": 1,
        "max_size": 3,
    },
    instance_types=["t4g.medium"],
    labels={
        "env": "dev"
    },
    ami_type="BOTTLEROCKET_ARM_64"
)


# Default managed EKS addons
aws.eks.Addon('coredns',
    cluster_name=cluster.name,
    addon_name='coredns',
    addon_version='', # empty string means latest
    #resolve_conflicts='OVERWRITE'
)
aws.eks.Addon('vpc-cni',
    cluster_name=cluster.name,
    addon_name='vpc-cni',
    addon_version='',
    #resolve_conflicts='OVERWRITE'
)
aws.eks.Addon('kube-proxy',
    cluster_name=cluster.name,
    addon_name='kube-proxy',
    addon_version='',
    #resolve_conflicts='OVERWRITE'
)

#pulumi.export('kubeconfig', cluster.kubeconfig)
pulumi.export('cluster_name', cluster.name)
pulumi.export('node_group_name', node_group.node_group_name)
