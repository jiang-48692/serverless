import json
import os
import uuid
from datetime import datetime, timezone
import boto3
from decimal import Decimal

# 環境変数
dynamodb = boto3.resource('dynamodb', region_name=os.environ['REGION'])
table = dynamodb.Table(os.environ['TABLE_NAME'])

# HTMLファイルの読み込み
def html_response():
    try:
        with open('index.html', 'r', encoding='utf-8') as f:
            html = f.read()
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html; charset=utf-8',
                'Access-Control-Allow-Origin': '*'
            },
            'body': html
        }
    except Exception as e:
        print(f"Error reading HTML file: {str(e)}")
        traceback.print_exc()
        return json_response({"error": "HTMLロードエラー"}, 500)

# JSONレスポンスのヘルパー関数
def json_response(body, status=200):
    return {
        'statusCode': status,
        'headers': {
            'Content-Type': 'application/json; charset=utf-8',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body, ensure_ascii=False)
    }

# Decimalをfloatに変換するヘルパー関数
def convert_decimals(obj):
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

# メイン関数
def lambda_handler(event, context):
    try:
        path = event.get("path", "/")
        method = event.get("httpMethod", "GET")
        body = event.get("body", "")
        print(f"[REQUEST] Path: {path}, Method: {method}")

        # リクエストボディのデバッグ出力
        if body:
            print(f"[REQUEST BODY] {body}")
        else:
            print("[REQUEST BODY] <empty>")
        
        # CORS対応
        if method == "OPTIONS":
            print("Handling CORS preflight")
            return json_response({"message": "OK"})
        
        # default処理
        if path == "/" and method == "GET":
            print("Handling HTML page request")
            return html_response()
        
        # DynamoDB送信処理
        elif path == "/submit" and method == "POST":
            print("Handling /submit request")
            try:
                # 空リクエスト確認
                if not body:
                    print("Body is empty in /submit")
                    return json_response({"error": "リクエストが空です"}, 400)
                
                data = json.loads(body)
                text = data.get("text", "").strip()
                print(f"Parsed text: '{text}'")
                
                if not text:
                    return json_response({"error": "テキストがからです"}, 400)
                
                # 验证文本长度
                if len(text) > 100:
                    return json_response({"error": "100以上入力されています"}, 400)
                
                now = datetime.now(timezone.utc).isoformat()
                item = {
                    "id": str(uuid.uuid4()),
                    "pk": "ECHO",
                    "text": text,
                    "created_at": now
                }
                
                print(f"Saving item to DynamoDB: {item}")
                table.put_item(Item=item)
                return json_response({"message": "DynamoDBに保存しました"})
                
            except json.JSONDecodeError as e:
                print(f"JSON decode error in /submit: {str(e)}")
                traceback.print_exc()
                return json_response({"error": f"JSON分析エラー: {str(e)}"}, 400)
            except Exception as e:
                print(f"Submit error: {str(e)}") 
                traceback.print_exc()
                return json_response({"error": "サーバー側エラー"}, 500)
        
        # DynamoDB取得処理
        elif path == "/latest" and method == "GET":
            print("Handling /latest request")
            try:
                response = table.query(
                    IndexName="CreatedAtIndex",
                    KeyConditionExpression='pk = :pk',
                    ExpressionAttributeValues={':pk': 'ECHO'},
                    ScanIndexForward=False,
                    Limit=10
                )
                
                print(f"DynamoDB response: {response}")
                items = convert_decimals(response.get("Items", []))
                return json_response(items)
                
            except Exception as e:
                print(f"Unhandled exception in /latest: {str(e)}")
                print(f"Latest error: {str(e)}") 
                return json_response({"error": "データ取得失敗"}, 500)
        
        else:
            print(f"Unknown path: {path} with method: {method}")
            return json_response({"error": "リクエスト失敗"}, 404)
    
    except Exception as e:
        print(f"Lambda handler error: {str(e)}")
        traceback.print_exc()
        return json_response({"error": "サーバーサイトのエラー"}, 500)