from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="contiguity_base",
    version="1.0.0",
    author="Contiguity",
    author_email="<help@contiguity.support>",
    description="The official Python SDK for Contiguity Base",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/contiguity/base-python",
    packages=find_packages(exclude=["tests", "examples"]),
    keywords=['python', 'contiguity', 'deta', 'base'],
    python_requires=">=3.6",
    install_requires=[
        "requests>=2.25.1",
    ],
)