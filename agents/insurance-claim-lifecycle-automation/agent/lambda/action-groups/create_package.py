import os
import io
import re
import json
import time
import boto3
import base64
import random
import string
import decimal
import requests

# DynamoDB boto3 resource and variable
dynamodb = boto3.resource('dynamodb',region_name=os.environ['AWS_REGION'])
existing_packages_table_name = os.environ['EXISTING_PACKAGES_TABLE_NAME']

# SNS boto3 clients and variables
sns_topic_arn = os.environ['SNS_TOPIC_ARN']
sns_client = boto3.client('sns')

# URL
url = os.environ['CUSTOMER_WEBSITE_URL']

def package_generator():
    print("Generating package ID")

    # Generate random characters and digits
    digits = ''.join(random.choice(string.digits) for _ in range(4))  # Generating 4 random digits
    chars = ''.join(random.choice(string.ascii_lowercase) for _ in range(3))  # Generating 3 random characters
    
    # Construct the pattern (1a23b-4c)
    pattern = f"{digits[0]}{chars[0]}{digits[1:3]}{chars[1]}-{digits[3]}{chars[2]}"

    return pattern

def collect_documents(package_id):
    print("Collecting Package Documents")

    subject = "New Package ID: " + package_id
    message = "Please upload your package document and required documents: " + url

    sns_client.publish(
        TopicArn=sns_topic_arn,
        Subject=subject,
        Message=message,
    )

def create_package(event):
    print("Creating Package")

    # TODO: Package creation logic
    generated_package = package_generator()

    # Update Excel data as needed (for example, add a new row with a new package)
    new_package_data = {'packageId': generated_package, 'line_noId': '123456789', 'status': 'Open', 'pendingDocuments': ['Drivers License', 'Registration', 'document']}  # Update column names and values

    # Update DynamoDB
    print("Updating DynamoDB")

    # Convert JSON document to DynamoDB format
    dynamodb_item = json.loads(json.dumps(new_package_data), parse_float=decimal.Decimal)
    existing_packages_table = dynamodb.Table(existing_packages_table_name)
    response = existing_packages_table.put_item(
        Item=dynamodb_item
    ) 

    collect_documents(generated_package)

    return {
        "response": [new_package_data]   
    }
 
def lambda_handler(event, context):
    response_code = 200
    action_group = event['actionGroup']
    api_path = event['apiPath']
    
    # API path routing
    if api_path == '/create-package':
        body = create_package(event)
    else:
        response_code = 400
        body = {"{}::{} is not a valid api, try another one.".format(action_group, api_path)}

    response_body = {
        'application/json': {
            'body': str(body)
        }
    }
    
    # Bedrock action group response format
    action_response = {
        "messageVersion": "1.0",
        "response": {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': event['httpMethod'],
            'httpStatusCode': response_code,
            'responseBody': response_body
        }
    }
 
    return action_response