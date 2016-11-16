# lambda-kube-aws-rtsync
Lambda function that will sync Kubernetes static routes to all private route tables within a VPC

Assumes the private route tables you are attempting to mirror have a `Name` tag with the prefix `private_`. Modify the following filter to match your needs.

```
private_rt_filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}, {'Name': 'tag:Name', 'Values': ['private_*']}]`
```
