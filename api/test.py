def handler(request):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': '{"status": "API test successful", "message": "Vercel serverless function working"}'
    }