from setuptools import setup, find_namespace_packages
import os.path

version_py = os.path.join(os.path.dirname(__file__), 'cocotbext', 'axi', 'version.py')
with open(version_py, 'r') as f:
    d = dict()
    exec(f.read(), d)
    version = d['__version__']

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="cocotbext-axi",
    author="Alex Forencich",
    author_email="alex@alexforencich.com",
    description="AXI modules for Cocotb",
    long_description=long_description,
    long_description_content_type='text/markdown',
    url="https://github.com/alexforencich/cocotbext-axi",
    download_url='http://github.com/alexforencich/cocotbext-axi/tarball/master',
    version=version,
    packages=find_namespace_packages(include=['cocotbext.*']),
    install_requires=['cocotb'],
    python_requires='>=3.6',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)"
    ]
)
