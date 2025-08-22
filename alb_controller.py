
import pulumi
import pulumi_aws as aws
import pulumi_kubernetes as k8s

# Tag subnets for EKS and ALB controller usage
def tag_subnets_for_eks_and_alb(vpc_id, public_subnet_ids, private_subnet_ids):
    # Tag public subnets for Kubernetes LoadBalancer
    for subnet_id in public_subnet_ids:
        aws.ec2.Tag(f"{subnet_id}-k8s-public",
            key="kubernetes.io/role/elb",
            value="1",
            resource_id=subnet_id
        )
        aws.ec2.Tag(f"{subnet_id}-cluster",
            key=f"kubernetes.io/cluster/{vpc_id}",
            value="shared",
            resource_id=subnet_id
        )
    # Tag private subnets for Kubernetes Internal LoadBalancer
    for subnet_id in private_subnet_ids:
        aws.ec2.Tag(f"{subnet_id}-k8s-private",
            key="kubernetes.io/role/internal-elb",
            value="1",
            resource_id=subnet_id
        )
        aws.ec2.Tag(f"{subnet_id}-cluster",
            key=f"kubernetes.io/cluster/{vpc_id}",
            value="shared",
            resource_id=subnet_id
        )

config = pulumi.Config()
cluster_name = config.require('cluster_name')
cluster_oidc_provider = config.require('cluster_oidc_provider')
cluster_oidc_arn = config.require('cluster_oidc_arn')

# IAM policy for AWS Load Balancer Controller (from AWS docs)
alb_policy_doc = aws.iam.get_policy_document(
    statements=[{
        "Effect": "Allow",
        "Action": [
            "acm:DescribeCertificate",
            "acm:ListCertificates",
            "acm:GetCertificate",
            "ec2:AuthorizeSecurityGroupIngress",
            "ec2:CreateSecurityGroup",
            "ec2:CreateTags",
            "ec2:DeleteTags",
            "ec2:DeleteSecurityGroup",
            "ec2:DescribeAccountAttributes",
            "ec2:DescribeAddresses",
            "ec2:DescribeInstances",
            "ec2:DescribeInstanceStatus",
            "ec2:DescribeInternetGateways",
            "ec2:DescribeNetworkInterfaces",
            "ec2:DescribeSecurityGroups",
            "ec2:DescribeSubnets",
            "ec2:DescribeTags",
            "ec2:DescribeVpcs",
            "ec2:ModifyInstanceAttribute",
            "ec2:ModifyNetworkInterfaceAttribute",
            "ec2:RevokeSecurityGroupIngress",
            "elasticloadbalancing:AddListenerCertificates",
            "elasticloadbalancing:AddTags",
            "elasticloadbalancing:CreateListener",
            "elasticloadbalancing:CreateLoadBalancer",
            "elasticloadbalancing:CreateRule",
            "elasticloadbalancing:CreateTargetGroup",
            "elasticloadbalancing:DeleteListener",
            "elasticloadbalancing:DeleteLoadBalancer",
            "elasticloadbalancing:DeleteRule",
            "elasticloadbalancing:DeleteTargetGroup",
            "elasticloadbalancing:DeregisterTargets",
            "elasticloadbalancing:DescribeListenerCertificates",
            "elasticloadbalancing:DescribeListeners",
            "elasticloadbalancing:DescribeLoadBalancers",
            "elasticloadbalancing:DescribeLoadBalancerAttributes",
            "elasticloadbalancing:DescribeRules",
            "elasticloadbalancing:DescribeSSLPolicies",
            "elasticloadbalancing:DescribeTags",
            "elasticloadbalancing:DescribeTargetGroups",
            "elasticloadbalancing:DescribeTargetGroupAttributes",
            "elasticloadbalancing:DescribeTargetHealth",
            "elasticloadbalancing:ModifyListener",
            "elasticloadbalancing:ModifyLoadBalancerAttributes",
            "elasticloadbalancing:ModifyRule",
            "elasticloadbalancing:ModifyTargetGroup",
            "elasticloadbalancing:ModifyTargetGroupAttributes",
            "elasticloadbalancing:RegisterTargets",
            "elasticloadbalancing:RemoveListenerCertificates",
            "elasticloadbalancing:RemoveTags",
            "elasticloadbalancing:SetIpAddressType",
            "elasticloadbalancing:SetSecurityGroups",
            "elasticloadbalancing:SetSubnets",
            "elasticloadbalancing:SetWebAcl",
            "iam:CreateServiceLinkedRole",
            "iam:GetServerCertificate",
            "iam:ListServerCertificates",
            "cognito-idp:DescribeUserPool",
            "cognito-idp:ListUserPoolClients",
            "cognito-idp:ListUserPools",
            "waf:GetWebACL",
            "waf:ListWebACLs",
            "waf-regional:GetWebACLForResource",
            "waf-regional:GetWebACL",
            "waf-regional:ListWebACLs",
            "waf-regional:ListResourcesForWebACL",
            "waf-regional:AssociateWebACL",
            "waf-regional:DisassociateWebACL",
            "wafv2:GetWebACL",
            "wafv2:ListWebACLs",
            "wafv2:ListResourcesForWebACL",
            "wafv2:AssociateWebACL",
            "wafv2:DisassociateWebACL",
            "shield:GetSubscriptionState",
            "shield:DescribeProtection",
            "shield:CreateProtection",
            "shield:DeleteProtection",
            "shield:DescribeSubscription",
            "shield:ListProtections"
        ],
        "Resource": "*"
    }]
)

alb_policy = aws.iam.Policy("alb-ingress-policy", policy=alb_policy_doc.json)

# IAM role for service account
alb_role = aws.iam.Role("alb-ingress-role",
    assume_role_policy=aws.iam.get_policy_document(
        statements=[{
            "Effect": "Allow",
            "Principal": {"Federated": cluster_oidc_arn},
            "Action": "sts:AssumeRoleWithWebIdentity",
            "Condition": {"StringEquals": {f"{cluster_oidc_provider}:sub": "system:serviceaccount:kube-system:aws-load-balancer-controller"}}
        }]
    ).json
)
aws.iam.RolePolicyAttachment("alb-ingress-policy-attach",
    role=alb_role.name,
    policy_arn=alb_policy.arn
)

# Kubernetes Service Account
alb_sa = k8s.core.v1.ServiceAccount("aws-load-balancer-controller-sa",
    metadata={
        "name": "aws-load-balancer-controller",
        "namespace": "kube-system",
        "annotations": {
            "eks.amazonaws.com/role-arn": alb_role.arn
        }
    }
)

# Helm chart for AWS Load Balancer Controller
alb_controller = k8s.helm.v3.Chart("aws-load-balancer-controller",
    k8s.helm.v3.ChartOpts(
        chart="aws-load-balancer-controller",
        fetch_opts=k8s.helm.v3.FetchOpts(
            repo="https://aws.github.io/eks-charts"
        ),
        namespace="kube-system",
        values={
            "clusterName": cluster_name,
            "serviceAccount": {
                "create": False,
                "name": "aws-load-balancer-controller"
            }
        }
    )
)
