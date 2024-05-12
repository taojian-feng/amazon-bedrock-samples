import os
import io
import re
import json
import time
import boto3
import base64
import string
import secrets
import requests

# DynamoDB boto3 clients and variables
dynamodb = boto3.resource('dynamodb',region_name=os.environ['AWS_REGION'])
dynamodb_client = boto3.client('dynamodb')
existing_packages_table_name = os.environ['EXISTING_PACKAGES_TABLE_NAME']

# SNS boto3 clients and variables
sns_topic_arn = os.environ['SNS_TOPIC_ARN']
sns_client = boto3.client('sns')

def get_named_parameter(event, name):
    return next(item for item in event['parameters'] if item['name'] == name)['value']

def get_named_property(event, name):
    return next(item for item in event['requestBody']['content']['application/json']['properties'] if item['name'] == name)['value']

def open_packages():
    print("Finding Open Packages")

    response = dynamodb_client.scan(
        TableName=existing_packages_table_name,
        FilterExpression='#s = :s',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={
            ':s': {'S': 'Open'}
        }
    )

    items = response.get('Items', [])
    # Extracting the 'packageId' attribute for items with 'status' equal to 'Open'
    open_package_ids = [item['packageId']['S'] for item in items if 'packageId' in item]

    return open_package_ids

def generate_reminder_id(length):
    print("Generate Reminder ID")
    # Define the characters that can be used in the random string
    characters = string.ascii_letters + string.digits
    
    # Generate a random string of the specified length
    random_string = ''.join(secrets.choice(characters) for _ in range(length))
    
    return random_string

def send_reminder(package_id, pending_documents):
    print("Send Reminder")

    subject = "Field Design Package ID: " + str(package_id)
    message = "Here is a reminder to upload your pending documents: " + str(pending_documents)
    print("Email Message: " + message)

    sns_client.publish(
        TopicArn=sns_topic_arn,
        Subject=subject,
        Message=message,
    )
    
    # Generate a random string of length 7 (to match the format '12a3456')
    reminder_id = generate_reminder_id(7)
    print("Reminder ID: " + str(reminder_id))

    return reminder_id

## Agent runtime Retrieve API with boto3 client ##
def notify_pending_documents(event):
    print("Notify Pending Documents")
    
    # Extracting packageId value from event parameters
    package_id = get_named_parameter(event, 'packageId')
    '''package_id = None
    for param in event.get('parameters', []):
        if param.get('name') == 'packageId': 
            package_id = param.get('value')
            break'''

    print("Package ID: " + str(package_id))

    if not package_id:
        return {
            'statusCode': 400,
            'response': 'Missing packageId parameter'
        }

    try:
        # Define the query parameters
        response = dynamodb_client.get_item(
            TableName=existing_packages_table_name,
            Key={
                'packageId': {'S': package_id}
            },
            ProjectionExpression='pendingDocuments'  # Retrieve only the 'pendingDocuments' attribute
        )
        
        # Extract pendingDocuments attribute from the DynamoDB response
        pending_documents_response = response.get('Item', {}).get('pendingDocuments', {}).get('L', [])

        # Transform the list of dictionaries to a list of strings
        pending_documents = [doc['S'] for doc in pending_documents_response]

        # Join the list of strings into a single string, separated by ", "
        formatted_pending_documents = ", ".join(pending_documents)

    except Exception as e:
        print(f"Error querying DynamoDB table: {e}")
        return []

    # Generate a random string of length 7 (to match the format '12a3456')
    reminder_tracking_id = send_reminder(package_id, formatted_pending_documents)
    print("Reminder tracking ID = " + str(reminder_tracking_id))

    return {
        'response': {
            'sendReminderTrackingId': reminder_tracking_id,  # Add appropriate tracking ID
            'sendReminderStatus': 'InProgress',  # Modify based on the actual reminder status
            'pendingDocuments': formatted_pending_documents
        }
    }
 
def lambda_handler(event, context):
    response_code = 200
    action_group = event['actionGroup']
    api_path = event['apiPath']

    if api_path == '/open-packages':
        body = open_packages() 
    elif api_path == '/packages/{packageId}/notify-pending-documents':
        body = notify_pending_documents(event)
    else:
        response_code = 400
        body = {"{}::{} is not a valid api, try another one.".format(action_group, api_path)}
    
    response_body = {
        'application/json': {
            'body': str(body)
        }
    }
    
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