import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

# Version number to __version__ variable
exec(open("gonioimsoft/version.py").read())

install_requires = [
        'numpy',
        'matplotlib',
        'tifffile',
        'pymmcore',
        'nidaqmx',
        'pyserial',
        'python-biosystfiles',
        ]

setuptools.setup(
    name="gonio-imsoft",
    version=__version__,
    author="Joni Kemppainen",
    author_email="joni.kemppainen@windowslive.com",
    description="Goniometric imaging software",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/musaprog/gonio-imsoft",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3) ",
        "Operating System :: Microsoft :: Windows",
        'Intended Audience :: Science/Research',
        "Environment :: Console",
    ],
    python_requires='>=3.6',
)
