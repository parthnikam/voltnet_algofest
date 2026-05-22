import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import market, users, websockets
from routers.websockets import orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(orchestrator.start_simulation_loop())
    yield


app = FastAPI(title="VoltNet Microgrid Core Engine", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(market.router)
app.include_router(websockets.router)


@app.get("/")
def read_root():
    return {"status": "VoltNet Engine Operational"}


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        body = detail
    else:
        body = {
            "status": "error",
            "message": str(detail),
            "data": None,
        }
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "message": "Request validation failed.",
            "data": {"errors": exc.errors()},
        },
    )
