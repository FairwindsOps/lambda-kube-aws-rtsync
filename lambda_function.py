import boto3
import re

#AWS region 
region = 'us-east-1'

#VPC id containing Kubernetes Cluster
vpc_id = 'vpc-xxxxxxxx'

#prefix of Kubernetes routes in route tables that should be synced
kube_routes_prefix = '100.96'

#Kubernetes cluster name
kube_cluster_name = 'working.example.com'

def get_routetables(cl, filters):
 route_table = cl.describe_route_tables(Filters=filters)
 route_table_ids = []
 route_table_routes = {}
 for rt in route_table['RouteTables']:
    route_table_ids.append(rt['RouteTableId'])
    route_table_routes[rt['RouteTableId']] = rt['Routes']
 return route_table_ids, route_table_routes

def get_kube_routes(cl, routes, route_prefix):
 kube_routes = {}
 kube_pattern = "^%s\.\d{1,3}\.\d{1,3}\/{1}\d{1,2}$" % route_prefix
 kube_regex = re.compile(kube_pattern)
 for route in routes:
    if route['State'] == 'active': 
        if 'DestinationCidrBlock' in route.keys() and re.match(kube_regex, route['DestinationCidrBlock']):
            kube_routes[route['DestinationCidrBlock']] = route['InstanceId']
    elif route['State'] == 'blackhole':
        kube_routes[route['DestinationCidrBlock']] = 'blackhole'
    else:
        next
 return kube_routes
 
def do (event, context):
 client = boto3.client('ec2', region_name=region)
 ec2 = boto3.resource('ec2')

 #drill route table tagged for KubernetesCluster
 kube_filters = [{'Name': 'tag:KubernetesCluster', 'Values': [kube_cluster_name]}]
 kube_routetable, kube_all_routes = get_routetables(client, kube_filters)

 #find definitive routes beginning with kube prefix from tagged route table
 definitive_kube_routes = get_kube_routes(client, kube_all_routes[kube_routetable[0]], kube_routes_prefix)

 #identify all private route tables in VPC
 private_rt_filters = [{'Name': 'vpc-id', 'Values': [vpc_id]}, {'Name': 'tag:Name', 'Values': ['private_*']}]
 private_routetables, private_all_routes = get_routetables(client, private_rt_filters)

 #remove kube routetable from list of private routables we're working on
 del private_routetables[private_routetables.index(kube_routetable[0])]
 del private_all_routes[kube_routetable[0]]
 
 #iterate through private route tables to sync routes
 for rt in private_routetables:
    
    #identify kube routes for this route table
    rt_kube_routes = get_kube_routes(client, private_all_routes[rt], kube_routes_prefix)   

    if definitive_kube_routes==rt_kube_routes:
        print "route table %s in sync with Kube route table %s" % (rt, kube_routetable[0])
        next
    else:
        print "route table %s not in sync" % rt
        
        #find any blackhole routes and remove them
        for key, value in rt_kube_routes.iteritems():
            if value == "blackhole":
                print "route %s is a blackhole" % key
                route = ec2.Route(rt, key)
                route.delete()
        
        #ensure definitive routes all exist in their proper state        
        for key, value in definitive_kube_routes.iteritems():
            if key in rt_kube_routes.keys():
                if value == rt_kube_routes[key]:
                    print "route %s is correctly pointed to instance %s" % (key, value)
                if value != rt_kube_routes[key]:
                    print "route %s is incorrectly pointed to instance %s instead of instance %s" % (key, definitive_kube_routes[key], value)
                    route = ec2.Route(rt, key)
                    route.replace(InstanceId=value)
            else:
                print "route %s doesn't exist" % key
                route_table = ec2.RouteTable(rt)
                route_table.create_route(DestinationCidrBlock=key, InstanceId=value)

