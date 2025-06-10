import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from botocore.exceptions import ClientError
from flask import Flask, request, jsonify
from decimal import Decimal

# 创建Flask应用
app = Flask(__name__)

# DynamoDB客户端
dynamodb = boto3.resource('dynamodb', region_name=os.environ['REGION'])
table = dynamodb.Table(os.environ['TODOS_TABLE_NAME'])

class DecimalEncoder(json.JSONEncoder):
    """处理DynamoDB返回的Decimal类型"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def convert_decimals(obj):
    """递归转换Decimal对象为float"""
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

@app.route('/', methods=['GET'])
def home():
    """首页"""
    return jsonify({
        "message": "Flask Lambda API with DynamoDB is running!",
        "version": "2.0.0",
        "database": "DynamoDB"
    })

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    try:
        # 尝试描述表以验证连接
        response = table.meta.client.describe_table(TableName=table.table_name)
        return jsonify({
            "status": "healthy", 
            "database": "DynamoDB",
            "table_status": response['Table']['TableStatus']
        })
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/todos', methods=['GET'])
def get_todos():
    """获取所有待办事项"""
    try:
        # 使用GSI按创建时间排序获取所有todos
        response = table.query(
            IndexName='CreatedAtIndex',
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={':pk': 'TODO'},
            ScanIndexForward=False  # 降序排列，最新的在前面
        )
        
        items = response.get('Items', [])
        # 转换Decimal类型
        todos = convert_decimals(items)
        
        return jsonify(todos)
    except Exception as e:
        print(f"Error getting todos: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/todos', methods=['POST'])
def create_todo():
    """创建新的待办事项"""
    try:
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({"error": "Title is required"}), 400
        
        # 生成唯一ID和时间戳
        todo_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        todo_item = {
            'id': todo_id,
            'pk': 'TODO',  # 分区键用于GSI
            'title': data['title'],
            'description': data.get('description', ''),
            'completed': False,
            'created_at': now,
            'updated_at': now
        }
        
        # 保存到DynamoDB
        table.put_item(Item=todo_item)
        
        # 转换Decimal类型后返回
        result = convert_decimals(todo_item)
        return jsonify(result), 201
        
    except Exception as e:
        print(f"Error creating todo: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/todos/<todo_id>', methods=['GET'])
def get_todo(todo_id):
    """获取特定待办事项"""
    try:
        response = table.get_item(Key={'id': todo_id})
        
        if 'Item' in response:
            todo = convert_decimals(response['Item'])
            return jsonify(todo)
        else:
            return jsonify({"error": "Todo not found"}), 404
            
    except Exception as e:
        print(f"Error getting todo {todo_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/todos/<todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """更新待办事项"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        # 构建更新表达式
        update_expression = "SET updated_at = :updated_at"
        expression_attribute_values = {
            ':updated_at': datetime.now(timezone.utc).isoformat()
        }
        
        if 'title' in data:
            update_expression += ", title = :title"
            expression_attribute_values[':title'] = data['title']
            
        if 'description' in data:
            update_expression += ", description = :description"
            expression_attribute_values[':description'] = data['description']
            
        if 'completed' in data:
            update_expression += ", completed = :completed"
            expression_attribute_values[':completed'] = bool(data['completed'])
        
        # 更新项目
        response = table.update_item(
            Key={'id': todo_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_attribute_values,
            ReturnValues='ALL_NEW'
        )
        
        if 'Attributes' in response:
            todo = convert_decimals(response['Attributes'])
            return jsonify(todo)
        else:
            return jsonify({"error": "Todo not found"}), 404
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            return jsonify({"error": "Todo not found"}), 404
        else:
            print(f"Error updating todo {todo_id}: {e}")
            return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"Error updating todo {todo_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/todos/<todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """删除待办事项"""
    try:
        # 先检查项目是否存在
        response = table.get_item(Key={'id': todo_id})
        
        if 'Item' not in response:
            return jsonify({"error": "Todo not found"}), 404
        
        # 删除项目
        table.delete_item(Key={'id': todo_id})
        
        return jsonify({"message": "Todo deleted successfully"})
        
    except Exception as e:
        print(f"Error deleting todo {todo_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/todos/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    try:
        # 获取所有todos
        response = table.query(
            IndexName='CreatedAtIndex',
            KeyConditionExpression='pk = :pk',
            ExpressionAttributeValues={':pk': 'TODO'}
        )
        
        items = response.get('Items', [])
        total_count = len(items)
        completed_count = sum(1 for item in items if item.get('completed', False))
        pending_count = total_count - completed_count
        
        return jsonify({
            "total": total_count,
            "completed": completed_count,
            "pending": pending_count,
            "completion_rate": round((completed_count / total_count * 100) if total_count > 0 else 0, 2)
        })
        
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

def lambda_handler(event, context):
    """Lambda函数入口点"""
    try:
        # 使用awsgi将API Gateway事件转换为WSGI格式
        from awsgi import response
        return response(app, event, context)
    except ImportError:
        # 如果没有awsgi，使用简单的处理方式
        return simple_lambda_handler(event, context)

def simple_lambda_handler(event, context):
    """简单的Lambda处理器（不使用awsgi）"""
    try:
        # 解析HTTP方法和路径
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        query_params = event.get('queryStringParameters') or {}
        
        # 处理路径参数
        path_params = event.get('pathParameters') or {}
        
        # 构建完整路径
        if path_params:
            for param_name, param_value in path_params.items():
                path = path.replace(f'{{{param_name}}}', param_value)
        
        # 模拟Flask请求上下文
        with app.test_request_context(
            path=path, 
            method=http_method,
            data=event.get('body'),
            headers=event.get('headers', {}),
            query_string=query_params
        ):
            try:
                # 调用Flask应用
                response = app.full_dispatch_request()
                
                return {
                    'statusCode': response.status_code,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key'
                    },
                    'body': response.get_data(as_text=True)
                }
            except Exception as e:
                print(f"Flask dispatch error: {e}")
                return {
                    'statusCode': 500,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({'error': str(e)})
                }
    except Exception as e:
        print(f"Lambda handler error: {e}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': f'Lambda handler error: {str(e)}'})
        }