from setuptools import setup, find_packages

setup(
    name='filegate',
    version='1.1.0',
    description='FileGate — connect, browse, pull and push files on remote file servers (SFTP, FTP, SMB)',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    python_requires='>=3.8',
    packages=find_packages(),
    install_requires=[
        'paramiko>=3.0.0',
        'smbprotocol>=1.12.0',
        'keyring>=24.0.0',
        'rich>=13.0.0',
    ],
    entry_points={
        'console_scripts': [
            'filegate=filegate.main:main',
            'fgate=filegate.main:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Topic :: Utilities',
        'Environment :: Console',
    ],
)
