from setuptools import setup, find_packages


with open("README.md", "r") as f:
    description = f.read()

setup(
    name="resistant_kafka_avataa",
    version="0.9.6",
    packages=find_packages(),
    install_requires=[
        "confluent-kafka[protobuf,schemaregistry]==2.10.0",
        "pydantic>=1.10.21,<3.0.0",
    ],
    long_description=description,
    long_description_content_type="text/markdown",
)

# to update version:
# 1.
# pip install wheel
# python setup.py bdist_wheel

# 2.
# pip install twine
# twine upload dist/*
