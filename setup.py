from setuptools import setup, find_packages


with open("README.md", "r") as f:
    description = f.read()

setup(
    name="resistant_kafka_avataa",
    version='0.9.8b10',
    packages=find_packages(exclude=["tests", "tests.*"]),
    install_requires=[
        "confluent-kafka[protobuf,schemaregistry]>=2.10.0,<3.0.0",
        "protobuf>=5.29.6,<8.0.0",
        "pydantic>=1.10.26,<3.0.0"
    ],
    long_description=description,
    long_description_content_type="text/markdown",
)

# Old version
# to update version:
# 1.
# pip install wheel
# python setup.py bdist_wheel

# 2.
# pip install twine
# twine upload dist/*


# Release to PyPI (use build, not setup.py directly):
# 1. Bump version above.
# 2. pip install build twine
# 3. python -m build
# 4. twine check dist/*
# 5. twine upload dist/*
