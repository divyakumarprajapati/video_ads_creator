from app.main import app 
import uvicorn

def main():
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info",
    )

if __name__ == "__main__":
    main()