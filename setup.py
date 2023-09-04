# See https://medium.com/nerd-for-tech/how-to-build-and-distribute-a-cli-tool-with-python-537ae41d9d78
from setuptools import setup, find_packages
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read()
setup(
    name='machine',
    version='1.0.0',
    author='Stirlingbridge',
    author_email='info@stirlingbridge.website',
    license='GNU Affero General Public License',
    description='Utility for creating and managing VMs',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/stirlingbridge/machine',
    py_modules=['machine'],
    packages=find_packages(),
    install_requires=[requirements],
    python_requires='>=3.8',
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': ['machine=machine.main:main'],
    }
)
