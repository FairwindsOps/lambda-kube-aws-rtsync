# lambda-kube-aws-rtsync

Lambda function that will sync Kubernetes static routes to other private route tables within a VPC


# Private Networking in AWS VPC

Private subnets within an Amazon VPC must be associated with a route table which defines its default route as a NAT Gateway (or NAT instance).  This allows for egress traffic to flow through the NAT appliance.  It is best practice to have a NAT appliance in each Availability Zone that your VPC spans. Subnets within a particular AZ should be associated with a route table whose default route is the NAT Gateway that resides within the same AZ.  Thus, if an Availability Zone is lost, instances within the remaining AZs will maintain their ability to send outbound traffic.

**tl;dr**:

If the private subnets within your VPC span 3 AZs, you will need 3 NAT Gateways and 3 route tables to ensure fault tolerance. Each route table will use a different NAT Gateway as its default route. Each private subnet will be associated with the route table that leverages the NAT Gateway in its corresponding AZ.

# Default Kubernetes `kubenet` in AWS VPC

Currently using the default `kubenet` network plugin with Kubernetes within an AWS VPC has unfortunate limitations.

Kubernetes will add one static route per node to a route table in your VPC tagged with the `KubernetesCluster` tag.  These look like /24 CIDRs which map to instance ids of the Kubernetes nodes in your cluster.  This allows pods to have routeable IP addresses within the VPC. Since there is one route per node, the number of static routes in your route table will be equal to the number of nodes in your cluster.

> One important limitation to note is that an AWS routing table cannot have more than 50 entries, which sets a limit of 50
> nodes per cluster. AWS support will sometimes raise the limit to 100, but performance limitations mean they are unlikely
> to raise it further.

Of concern here is the limitation that only one route table can be tagged `KubernetesCluster`. Tagging multiple route tables will actually prevent Kubernetes from modifying any routes. With only a single functioning route table, you are forced to associate _all_ subnets (regardless of AZ) with that particular route table.  Thus, you are forcing all subnets, in all Availability Zones to use a single NAT Gateway in an AZ they may or may not belong to.  This creates a single point of failure and network latency on outbound calls.

**tl;dr**:

![stuff's broken yo](https://cdn.meme.am/instances/45655627.jpg)

# A Workaround

Let's accept the fact that, currently, the limitation is that Kubernetes can only manage a single AWS route table.  We need a way to mirror or sync the Kubernetes specific routes to our other private route tables so that all our AZs have full functionality.  

Copying all the routes over by hand: right out. Rather, let's write a Lambda function to do this for us.  Since a new route is created/removed whenever a new Kubernetes node is initialized/terminated, we already have a pretty good trigger available.  We can use scaling activities on the Kubernetes node Autoscaling Group to trigger our Lambda function.

# Variables

####AWS region 
`region = 'us-east-1'`

####VPC id containing Kubernetes Cluster
`vpc_id = 'vpc-xxxxxxxx'`

####prefix of Kubernetes routes in route tables that should be synced
`kube_routes_prefix = '100.96'`

####Kubernetes cluster name
`kube_cluster_name = 'working.example.com'`

####filter that defines which route tables should be mirrors of the Kubernetes managed route table
`
private_rt_filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}, {'Name': 'tag:Name', 'Values': ['private_*']}]
`

# IAM policy for Lambda Function 

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "ec2:DescribeRouteTables",
                "ec2:ReplaceRoute",
                "ec2:CreateRoute",
                "ec2:DeleteRoute"
            ],
            "Resource": "*",
            "Effect": "Allow"
        }
    ]
}
```

# Autoscaling trigger for Lambda Function

1. Under `SNS`, select `Create topic` from dashboard
 - enter `Topic name` : `kube-node-scaling-actions`
 - enter `Display name` (max of 10 characters)
 - click `Create topic`

2. Under `EC2` > `Auto Scaling Groups`, select the ASG managing your Kubernetes nodes
 - On the `Notifications` tab 
 - click `Create Notification`
  - choose the SNS topic created above from the drop down box
  - make sure `launch` and `terminate` boxed are ticked
  - click `Save`
  
4. Under `Lambda` > `Functions`, select the Lambda function created
 - On the `Triggers` tab
 - click `Add trigger`
  - click the empty dotted-box icon
  - choose `SNS`
  - choose the `SNS topic` created above from the drop down box
  - make sure `Enable trigger` is checked
  - click `Submit`


