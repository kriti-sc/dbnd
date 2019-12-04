from os import path

import setuptools

from setuptools.config import read_configuration


BASE_PATH = path.dirname(__file__)
CFG_PATH = path.join(BASE_PATH, "setup.cfg")

config = read_configuration(CFG_PATH)
version = config["metadata"]["version"]

setuptools.setup(
    name="dbnd-airflow",
    package_dir={"": "src"},
    install_requires=[
        "dbnd==" + version,
        "apache-airflow==1.10.3",
        # otherwise airflow dependencies are broken
        "flask==1.0.3",
        "future>=0.16.0, <0.17",
        "jinja2==2.10.0",
        "werkzeug<0.15.0,>=0.14.1",
        "sqlalchemy_utc",
        "sqlalchemy_utils",
    ],
    extras_require=dict(
        tests=[
            # azure
            "azure-storage-blob",
            # aws
            "httplib2>=0.9.2",
            "boto3",
            "s3fs",
            # gcs
            "httplib2>=0.9.2",
            "google-api-python-client>=1.6.0, <2.0.0dev",
            "google-auth>=1.0.0, <2.0.0dev",
            "google-auth-httplib2>=0.0.1",
            "google-cloud-container>=0.1.1",
            "PyOpenSSL",
            "pandas-gbq",
            # docker
            "docker~=3.0",
            # k8s
            "kubernetes==9.0.0",
            "cryptography>=2.0.0",
        ]
    ),
    entry_points={"dbnd": ["dbnd-airflow = dbnd_airflow._plugin"]},
)
