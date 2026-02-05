"""Setup script for Personal Outreach Agent."""

from setuptools import setup, find_packages

setup(
    name="personal-outreach-agent",
    version="0.1.0",
    description="Personal Outreach Agent for Common Notary Apostille",
    author="Common Notary Apostille",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "sqlalchemy>=2.0.0",
        "click>=8.1.0",
        "rich>=13.6.0",
        "httpx>=0.25.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "python-dateutil>=2.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "outreach-agent=src.cli:main",
        ],
    },
    python_requires=">=3.10",
)
