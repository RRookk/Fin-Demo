"""Fin Demo — A lightweight API demo showcasing Fin-train and Finogrid.

Fin-train: Financial LLM fine-tuning framework (sentiment analysis, stock forecasting, RAG)
Finogrid: B2B stablecoin payout + Agent-to-Agent micro-transaction platform

This demo uses SQLite and simulated AI to run locally with zero external dependencies.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="fin-demo",
    version="0.1.0",
    author="Fin Team",
    description="Fin-train & Finogrid API Demo",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-username/fin-demo",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
