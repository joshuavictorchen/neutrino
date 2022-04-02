from setuptools import setup, find_packages

setup(
    name="neutrino",
    version="0.0",
    packages=find_packages(),
    entry_points={"console_scripts": ["neutrino = neutrino.main:main"]},
    install_requires=[
        "requests==2.27.1",
        "websocket-client==1.2.3",
        "GitPython==3.1.24",
        "pandas==1.2.2",
        "DateTime==4.3",
        "matplotlib==3.4.3",
        "numpy==1.20.1",
        "python-dateutil==2.8.1",
        "PyYAML==6.0",
        "pandasql",  # temporary requirement until sqldf functions are replaced
    ],
)
