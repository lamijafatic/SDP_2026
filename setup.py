from setuptools import setup, find_packages

setup(
    name="arbor-pm",
    version="0.1.0",
    description="Python Package Manager with SAT-Based Dependency Resolution",
    packages=find_packages(),
    package_data={"": ["data/*.json"]},
    include_package_data=True,
    install_requires=[
        "python-sat>=0.1.8",
        "toml>=0.10",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "arbor=cli.main:main",
        ],
    },
)
