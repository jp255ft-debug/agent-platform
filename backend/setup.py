from setuptools import setup, find_packages

setup(
    name="agent-platform-backend",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        "sqlalchemy[asyncio]>=2.0.0",
        "asyncpg>=0.29.0",
        "alembic>=1.13.0",
        "redis[hiredis]>=5.0.0",
        "aiokafka>=0.10.0",
        "web3>=6.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "httpx>=0.25.0",
        "bcrypt>=4.1.0",
    ],
)
