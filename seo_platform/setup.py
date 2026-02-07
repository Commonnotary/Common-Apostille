"""Setup script for the SEO & AI Monitoring Platform."""

from setuptools import setup, find_packages

setup(
    name="seo-platform-common-notary",
    version="1.0.0",
    description="SEO & AI Monitoring Platform for Common Notary Apostille",
    author="Common Notary Apostille",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "seo-platform=cli:cli",
        ],
    },
)
