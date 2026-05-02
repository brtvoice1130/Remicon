def handler(request):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": {
            "message": "Hello from Vercel Python!",
            "path": request.get("path", "unknown"),
            "method": request.get("method", "unknown")
        }
    }