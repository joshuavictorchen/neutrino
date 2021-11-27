from setuptools import setup, find_packages

setup(
    name="neutrino",
    version="0.0",
    packages=find_packages(),
    entry_points={"console_scripts": ["neutrino = neutrino.main:main"]},
    install_requires=[
        "requests",
        "websocket",
        "gitpython",
        "pandas",
        "datetime",
        "matplotlib",
        "numpy",
        "python-dateutil",
        "pyyaml",
        "sphinx",
    ],
)
